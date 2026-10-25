import logging
import sqlite3
import requests
from bs4 import BeautifulSoup
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

# إعداد السجلات
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# --- إعداد قاعدة البيانات ---
def init_db():
    conn = sqlite3.connect('tracked_products.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            url TEXT,
            title TEXT,
            price TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# دالة لجلب السعر واسم المنتج
def fetch_product_details(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9"
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            title_element = soup.find(id='productTitle')
            title = title_element.get_text().strip() if title_element else "منتج بدون عنوان"
            
            price_element = soup.find('span', {'class': 'a-offscreen'})
            price = price_element.get_text().strip() if price_element else "غير متوفر"
            
            return title[:40] + "...", price
        else:
            return None, None
    except Exception:
        return None, None

# دالة الترحيب
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.effective_user.first_name
    
    keyboard = [
        [InlineKeyboardButton("➕ إضافة رابط منتج للتتبع", callback_data='add_product')],
        [InlineKeyboardButton("📋 قائمة المنتجات المتابعة", callback_data='list_products')],
        [InlineKeyboardButton("❓ كيفية الاستخدام", callback_data='help')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_text = (
        f"أهلاً بك يا {user_name} في **بوت تتبع الأسعار الذكي**! 🛒\n\n"
        f"يمكنني حفظ ومراقبة أسعار منتجاتك وتنبيهك باستمرار عند تغيرها.\n"
        f"اختر ما تريد القيام به:"
    )
    
    await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode='Markdown')

# التعامل مع الأزرار
async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    
    if query.data == 'add_product':
        await query.edit_message_text(
            text="🔗 **إضافة منتج جديد:**\n\nأرسل لي رابط المنتج الآن، وسأقوم بحفظه في قاعدة البيانات وتتبع سعره دورياً.",
            parse_mode='Markdown'
        )
    elif query.data == 'list_products':
        conn = sqlite3.connect('tracked_products.db')
        cursor = conn.cursor()
        cursor.execute('SELECT id, title, price, url FROM products WHERE user_id = ?', (user_id,))
        rows = cursor.fetchall()
        conn.close()
        
        if rows:
            text = "📋 **قائمة منتجاتك المتابعة:**\nاختر المنتج الذي تريد حذفه من القائمة أدناه:"
            keyboard = []
            for prod_id, title, price, url in rows:
                # إنشاء زر لكل منتج يحتوي على اسم المنتج وسعره، وcallback_data يحمل رقم المنتج لحذفه
                button_text = f"🗑️ حذف: {title[:25]} ({price})"
                keyboard.append([InlineKeyboardButton(button_text, callback_data=f'delete_{prod_id}')])
            
            # زر للرجوع للقائمة الرئيسية
            keyboard.append([InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data='main_menu')])
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(text=text, reply_markup=reply_markup, parse_mode='Markdown')
        else:
            keyboard = [[InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data='main_menu')]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text="📋 **قائمة التتبع:**\n\nليس لديك أي منتجات محفوظة حالياً.", reply_markup=reply_markup, parse_mode='Markdown')
            
    elif query.data.startswith('delete_'):
        # استخراج رقم المنتج المراد حذفه
        prod_id = query.data.split('_')[1]
        
        conn = sqlite3.connect('tracked_products.db')
        cursor = conn.cursor()
        cursor.execute('DELETE FROM products WHERE id = ? AND user_id = ?', (prod_id, user_id))
        conn.commit()
        conn.close()
        
        await query.answer("تم حذف المنتج بنجاح! ✅", show_alert=True)
        
        # تحديث القائمة بعد الحذف
        conn = sqlite3.connect('tracked_products.db')
        cursor = conn.cursor()
        cursor.execute('SELECT id, title, price, url FROM products WHERE user_id = ?', (user_id,))
        rows = cursor.fetchall()
        conn.close()
        
        if rows:
            text = "📋 **قائمة منتجاتك المتابعة:**\nاختر المنتج الذي تريد حذفه من القائمة أدناه:"
            keyboard = []
            for p_id, title, price, url in rows:
                keyboard.append([InlineKeyboardButton(f"🗑️ حذف: {title[:25]} ({price})", callback_data=f'delete_{p_id}')])
            keyboard.append([InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data='main_menu')])
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text=text, reply_markup=reply_markup, parse_mode='Markdown')
        else:
            keyboard = [[InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data='main_menu')]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text="📋 **قائمة التتبع:**\n\nتم حذف كل المنتجات. لم يتبق لديك منتجات محفوظة.", reply_markup=reply_markup, parse_mode='Markdown')

    elif query.data == 'main_menu':
        keyboard = [
            [InlineKeyboardButton("➕ إضافة رابط منتج للتتبع", callback_data='add_product')],
            [InlineKeyboardButton("📋 قائمة المنتجات المتابعة", callback_data='list_products')],
            [InlineKeyboardButton("❓ كيفية الاستخدام", callback_data='help')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            text="🛒 **القائمة الرئيسية:**\n\nاختر ما تريد القيام به:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

    elif query.data == 'help':
        keyboard = [[InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data='main_menu')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            text="❓ **كيفية الاستخدام:**\n\n1️⃣ أرسل رابط المنتج مباشرة.\n2️⃣ سيقوم البوت باستخراج السعر وحفظه.\n3️⃣ اضغط على 'قائمة المنتجات المتابعة' لرؤية أو حذف منتجاتك.",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

# التعامل مع الروابط وحفظها
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id
    
    if text.startswith("http://") or text.startswith("https://"):
        wait_msg = await update.message.reply_text("⏳ جاري استخراج بيانات المنتج وحفظها في قاعدة البيانات...")
        
        title, price = fetch_product_details(text)
        
        if title and price:
            conn = sqlite3.connect('tracked_products.db')
            cursor = conn.cursor()
            cursor.execute('INSERT INTO products (user_id, url, title, price) VALUES (?, ?, ?, ?)', 
                           (user_id, text, title, price))
            conn.commit()
            conn.close()
            
            reply = (
                f"✅ **تم حفظ المنتج بنجاح وتفعيل التتبع الدوري!**\n\n"
                f"📦 **الاسم:** {title}\n"
                f"💰 **السعر الحالي:** `{price}`\n\n"
                f"يمكنك معاينة أو حذف منتجاتك بالضغط على /start"
            )
        else:
            reply = f"⚠️ تم استلام الرابط ولكن تعذر جلب السعر تلقائياً:\n`{text}`"
            
        await wait_msg.edit_text(reply, parse_mode='Markdown')
    else:
        await update.message.reply_text("⚠️ أرسل رابطاً صحيحاً يبدأ بـ http أو استخدم /start", parse_mode='Markdown')

# --- دالة الفحص الدوري للأسعار في الخلفية ---
async def check_prices(context: ContextTypes.DEFAULT_TYPE):
    conn = sqlite3.connect('tracked_products.db')
    cursor = conn.cursor()
    cursor.execute('SELECT id, user_id, url, title, price FROM products')
    rows = cursor.fetchall()
    
    for row in rows:
        prod_id, user_id, url, title, old_price = row
        _, new_price = fetch_product_details(url)
        
        if new_price and new_price != old_price:
            cursor.execute('UPDATE products SET price = ? WHERE id = ?', (new_price, prod_id))
            conn.commit()
            
            alert_text = (
                f"🚨 **تنبيه تغيير السعر!** 📉📈\n\n"
                f"📦 **المنتج:** {title}\n"
                f"🏷️ **السعر القديم:** `{old_price}`\n\n"
                f"💰 **السعر الجديد:** `{new_price}`\n\n"
                f"🔗 [رابط المنتج]({url})"
            )
            try:
                await context.bot.send_message(chat_id=user_id, text=alert_text, parse_mode='Markdown', disable_web_page_preview=True)
            except Exception as e:
                print(f"فشل إرسال التنبيه للمستخدم: {e}")
                
    conn.close()

if __name__ == '__main__':
    TOKEN = "8450807913:AAEm0Cwu6lNvI5qeApVMC0EIP9yqNLVH69U"
    
    app = ApplicationBuilder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_click))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # جدولة دالة الفحص الدوري كل ساعة
    job_queue = app.job_queue
    job_queue.run_repeating(check_prices, interval=3600, first=10)
    
    print("البوت الاحترافي المتكامل (مع التتبع والحذف) يعمل الآن...")
    app.run_polling()

