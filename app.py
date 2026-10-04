import os
import json
from flask import Flask, render_template_string, request, jsonify

app = Flask(__name__)

# ----------------- 1. تحميل القرآن والتفسير -----------------
# ملاحظة: الملفات الآن في المستوى الرئيسي (بدون مجلد data)
QURAN_PATH = 'quran.json'
TAFSIR_PATH = 'tafsir_saadi.json'

def load_json(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading {filepath}: {e}")
        return []

quran_data = load_json(QURAN_PATH)
tafsir_list = load_json(TAFSIR_PATH)

# تحويل التفسير إلى قاموس للبحث السريع
tafsir_map = {}
for item in tafsir_list:
    key = (item.get('surah'), item.get('ayah'))
    tafsir_map[key] = item.get('text', 'لا يوجد نص تفسير')

# ----------------- 2. قائمة الكتب المتاحة -----------------
BOOKS = {
    'quran': 'القرآن الكريم والتفسير',
    'bukhari': 'صحيح البخاري',
    'muslim': 'صحيح مسلم',
    'abudawud': 'سنن أبي داود',
    'tirmidhi': 'جامع الترمذي',
    'nasai': 'سنن النسائي',
    'ibnmajah': 'سنن ابن ماجه',
    'malik': 'موطأ مالك',
    'ahmed': 'مسند أحمد',
    'darimi': 'سنن الدارمي',
    'riyad_assalihin': 'رياض الصالحين',
    'aladab_almufrad': 'الأدب المفرد',
    'bulugh_almaram': 'بلوغ المرام',
    'mishkat_almasabih': 'مشكاة المصابيح',
    'shamail_muhammadiyah': 'الشمائل المحمدية'
}

# ذاكرة مؤقتة لتخزين الكتب في الرام لتسريع البحث
loaded_books_cache = {}

def load_hadith_book(book_id):
    if book_id in loaded_books_cache:
        return loaded_books_cache[book_id]

    all_hadiths = []
    
    # الحالة 1: الكتب التسعة (ملف واحد كبير في المستوى الرئيسي)
    single_file_path = f'{book_id}.json'
    if os.path.exists(single_file_path):
        data = load_json(single_file_path)
        all_hadiths = data.get('hadiths', [])
    
    # الحالة 2: الكتب الأخرى (مجلد به ملفات صغيرة في المستوى الرئيسي)
    elif os.path.isdir(book_id):
        folder_path = book_id
        files = os.listdir(folder_path)
        # ترتيب الملفات رقمياً (1.json, 2.json, ...)
        files = sorted(
            [f for f in files if f.endswith('.json')],
            key=lambda x: int(x.split('.')[0]) if x.split('.')[0].isdigit() else 999
        )
        
        for filename in files:
            filepath = os.path.join(folder_path, filename)
            data = load_json(filepath)
            all_hadiths.extend(data.get('hadiths', []))
    
    loaded_books_cache[book_id] = all_hadiths
    return all_hadiths

# ----------------- 3. المسارات (Routes) -----------------
@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE, books=BOOKS)

@app.route('/search')
def search():
    book_id = request.args.get('book', 'quran')
    query = request.args.get('query', '').strip()
    surah = request.args.get('surah', type=int)

    results = []

    if book_id == 'quran':
        if surah:
            for item in quran_data:
                if item.get('surah') == surah:
                    ayah_num = item.get('ayah')
                    results.append({
                        'type': 'quran',
                        'surah': surah,
                        'ayah': ayah_num,
                        'text': item.get('text', ''),
                        'tafsir': tafsir_map.get((surah, ayah_num), "لا يوجد تفسير مسجل.")
                    })
    else:
        # البحث في كتب الحديث
        hadiths = load_hadith_book(book_id)
        if not hadiths:
            return jsonify({'error': 'لم يتم العثور على بيانات هذا الكتاب.'})
        
        count = 0
        for h in hadiths:
            arabic_text = h.get('arabic', '')
            if query in arabic_text:
                results.append({
                    'type': 'hadith',
                    'id': h.get('idInBook', ''),
                    'text': arabic_text,
                    'narrator': h.get('english', {}).get('narrator', '')
                })
                count += 1
                if count >= 50:  # نكتفي بـ 50 نتيجة للسرعة
                    break

    return jsonify(results)

# ----------------- 4. واجهة المستخدم (HTML) -----------------
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>الموسوعة الإسلامية الشاملة</title>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f4f4f9; margin: 0; padding: 20px; color: #333; }
        .container { max-width: 800px; margin: 0 auto; background: white; padding: 20px; border-radius: 10px; box-shadow: 0 4px 8px rgba(0,0,0,0.1); }
        h1 { text-align: center; color: #2c3e50; margin-bottom: 20px; }
        .search-box { display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 20px; }
        select, input { padding: 10px; font-size: 16px; border: 1px solid #ccc; border-radius: 5px; flex: 1; min-width: 150px; }
        button { padding: 10px 20px; font-size: 16px; background-color: #27ae60; color: white; border: none; border-radius: 5px; cursor: pointer; }
        button:hover { background-color: #219150; }
        .result { border-bottom: 1px solid #eee; padding: 15px 0; }
        .hadith-info { display: flex; justify-content: space-between; color: #7f8c8d; font-size: 14px; margin-bottom: 5px; }
        .hadith-text { font-size: 18px; line-height: 1.8; margin-bottom: 10px; white-space: pre-wrap; }
        .copy-btn { background-color: #3498db; padding: 5px 10px; font-size: 14px; }
        .copy-btn:hover { background-color: #2980b9; }
        .narrator { font-weight: bold; color: #e67e22; font-size: 14px; margin-bottom: 5px; }
        .tafsir { background-color: #f9f9f9; border-top: 2px solid #28a745; margin-top: 10px; padding: 10px; }
        .hidden { display: none; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🕌 الموسوعة الإسلامية الشاملة 📚</h1>
        <div class="search-box">
            <select id="bookSelect" onchange="toggleSearchMode()">
                {% for key, value in books.items() %}
                <option value="{{ key }}">{{ value }}</option>
                {% endfor %}
            </select>
            
            <!-- خاص بالقرآن -->
            <select id="surahSelect" class="hidden">
                <option value="1">الفاتحة</option>
                <option value="2">البقرة</option>
                <option value="3">آل عمران</option>
                <option value="4">النساء</option>
                <option value="5">المائدة</option>
                <option value="6">الأنعام</option>
                <option value="7">الأعراف</option>
                <option value="8">الأنفال</option>
                <option value="9">التوبة</option>
                <option value="10">يونس</option>
                <option value="11">هود</option>
                <option value="12">يوسف</option>
                <option value="13">الرعد</option>
                <option value="14">إبراهيم</option>
                <option value="15">الحجر</option>
                <option value="16">النحل</option>
                <option value="17">الإسراء</option>
                <option value="18">الكهف</option>
                <option value="19">مريم</option>
                <option value="20">طه</option>
                <option value="21">الأنبياء</option>
                <option value="22">الحج</option>
                <option value="23">المؤمنون</option>
                <option value="24">النور</option>
                <option value="25">الفرقان</option>
                <option value="26">الشعراء</option>
                <option value="27">النمل</option>
                <option value="28">القصص</option>
                <option value="29">العنكبوت</option>
                <option value="30">الروم</option>
                <option value="31">لقمان</option>
                <option value="32">السجدة</option>
                <option value="33">الأحزاب</option>
                <option value="34">سبأ</option>
                <option value="35">فاطر</option>
                <option value="36">يس</option>
                <option value="37">الصافات</option>
                <option value="38">ص</option>
                <option value="39">الزمر</option>
                <option value="40">غافر</option>
                <option value="41">فصلت</option>
                <option value="42">الشورى</option>
                <option value="43">الزخرف</option>
                <option value="44">الدخان</option>
                <option value="45">الجاثية</option>
                <option value="46">الأحقاف</option>
                <option value="47">محمد</option>
                <option value="48">الفتح</option>
                <option value="49">الحجرات</option>
                <option value="50">ق</option>
                <option value="51">الذاريات</option>
                <option value="52">الطور</option>
                <option value="53">النجم</option>
                <option value="54">القمر</option>
                <option value="55">الرحمن</option>
                <option value="56">الواقعة</option>
                <option value="57">الحديد</option>
                <option value="58">المجادلة</option>
                <option value="59">الحشر</option>
                <option value="60">الممتحنة</option>
                <option value="61">الصف</option>
                <option value="62">الجمعة</option>
                <option value="63">المنافقون</option>
                <option value="64">التغابن</option>
                <option value="65">الطلاق</option>
                <option value="66">التحريم</option>
                <option value="67">الملك</option>
                <option value="68">القلم</option>
                <option value="69">الحاقة</option>
                <option value="70">المعارج</option>
                <option value="71">نوح</option>
                <option value="72">الجن</option>
                <option value="73">المزمل</option>
                <option value="74">المدثر</option>
                <option value="75">القيامة</option>
                <option value="76">الإنسان</option>
                <option value="77">المرسلات</option>
                <option value="78">النبأ</option>
                <option value="79">النازعات</option>
                <option value="80">عبس</option>
                <option value="81">التكوير</option>
                <option value="82">الانفطار</option>
                <option value="83">المطففين</option>
                <option value="84">الانشقاق</option>
                <option value="85">البروج</option>
                <option value="86">الطارق</option>
                <option value="87">الأعلى</option>
                <option value="88">الغاشية</option>
                <option value="89">الفجر</option>
                <option value="90">البلد</option>
                <option value="91">الشمس</option>
                <option value="92">الليل</option>
                <option value="93">الضحى</option>
                <option value="94">الشرح</option>
                <option value="95">التين</option>
                <option value="96">العلق</option>
                <option value="97">القدر</option>
                <option value="98">البينة</option>
                <option value="99">الزلزلة</option>
                <option value="100">العاديات</option>
                <option value="101">القارعة</option>
                <option value="102">التكاثر</option>
                <option value="103">العصر</option>
                <option value="104">الهمزة</option>
                <option value="105">الفيل</option>
                <option value="106">قريش</option>
                <option value="107">الماعون</option>
                <option value="108">الكوثر</option>
                <option value="109">الكافرون</option>
                <option value="110">النصر</option>
                <option value="111">المسد</option>
                <option value="112">الإخلاص</option>
                <option value="113">الفلق</option>
                <option value="114">الناس</option>
            </select>

            <!-- خاص بالحديث -->
            <input type="text" id="searchInput" class="hidden" placeholder="ابحث عن كلمة أو حديث...">
            
            <button onclick="doSearch()">بحث 🔍</button>
        </div>
        <div id="results"></div>
    </div>

    <script>
        function toggleSearchMode() {
            const book = document.getElementById('bookSelect').value;
            const surahSelect = document.getElementById('surahSelect');
            const searchInput = document.getElementById('searchInput');
            
            if (book === 'quran') {
                surahSelect.classList.remove('hidden');
                searchInput.classList.add('hidden');
            } else {
                surahSelect.classList.add('hidden');
                searchInput.classList.remove('hidden');
            }
        }

        async function doSearch() {
            const book = document.getElementById('bookSelect').value;
            const query = document.getElementById('searchInput').value;
            const surah = document.getElementById('surahSelect').value;
            const resultsDiv = document.getElementById('results');
            
            resultsDiv.innerHTML = '<p style="text-align:center;">جاري البحث...</p>';

            const response = await fetch(`/search?book=${book}&query=${encodeURIComponent(query)}&surah=${surah}`);
            const data = await response.json();

            if (data.error) {
                resultsDiv.innerHTML = `<p style="color:red;text-align:center;">${data.error}</p>`;
                return;
            }

            if (data.length === 0) {
                resultsDiv.innerHTML = '<p style="text-align:center;">لا توجد نتائج مطابقة.</p>';
                return;
            }

            let html = '';
            data.forEach(item => {
                if (item.type === 'quran') {
                    html += `<div class="result">
                                <strong>سورة ${item.surah} آية ${item.ayah}:</strong><br>
                                <p>${item.text}</p>
                                <div class="tafsir"><strong>التفسير:</strong><br>${item.tafsir}</div>
                             </div>`;
                } else {
                    html += `<div class="result">
                                <div class="hadith-info">
                                    <span>رقم الحديث: ${item.id}</span>
                                    <button class="copy-btn" onclick="copyText(this)">نسخ 📋</button>
                                </div>
                                ${item.narrator ? `<div class="narrator">${item.narrator}</div>` : ''}
                                <div class="hadith-text">${item.text}</div>
                             </div>`;
                }
            });
            resultsDiv.innerHTML = html;
        }

        function copyText(btn) {
            const text = btn.closest('.result').querySelector('.hadith-text').innerText;
            navigator.clipboard.writeText(text).then(() => {
                const originalText = btn.innerText;
                btn.innerText = 'تم النسخ ✅';
                setTimeout(() => { btn.innerText = originalText; }, 2000);
            });
        }
        
        // استدعاء الدالة عند التحميل الأول
        toggleSearchMode();
    </script>
</body>
</html>
"""

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
