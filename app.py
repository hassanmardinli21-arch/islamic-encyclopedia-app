import os
import json
from flask import Flask, render_template_string, request, jsonify

app = Flask(__name__)

# قائمة الكتب المتاحة
BOOKS = {
    'bukhari': 'صحيح البخاري',
    'muslim': 'صحيح مسلم',
    'abudawud': 'سنن أبي داود',
    'tirmidhi': 'جامع الترمذي',
    'nasai': 'سنن النسائي',
    'ibnmajah': 'سنن ابن ماجه',
    'malik': 'موطأ مالك',
    'ahmed': 'مسند أحمد',
    'darimi': 'سنن الدارمي'
}

# ذاكرة مؤقتة لتخزين الكتب في الرام لتسريع البحث
loaded_books = {}

def load_book(book_id):
    if book_id in loaded_books:
        return loaded_books[book_id]
    
    filepath = f'data/{book_id}.json'
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
            loaded_books[book_id] = data
            return data
    except Exception as e:
        print(f"Error loading {filepath}: {e}")
        return None

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE, books=BOOKS)

@app.route('/search')
def search():
    book_id = request.args.get('book', 'bukhari')
    query = request.args.get('query', '').strip()
    
    book_data = load_book(book_id)
    if not book_data:
        return jsonify({'error': 'عذراً، لم يتم العثور على بيانات هذا الكتاب.'})

    results = []
    hadiths = book_data.get('hadiths', [])
    
    # إذا كان البحث فارغاً، نعرض أول 20 حديثاً
    if not query:
        for h in hadiths[:20]:
            results.append(format_hadith(h))
    else:
        for h in hadiths:
            arabic_text = h.get('arabic', '')
            if query in arabic_text:
                results.append(format_hadith(h))
                if len(results) >= 50: # نكتفي بـ 50 نتيجة للسرعة
                    break

    return jsonify(results)

def format_hadith(h):
    return {
        'id': h.get('idInBook', ''),
        'text': h.get('arabic', ''),
        'narrator': h.get('english', {}).get('narrator', '')
    }

# ----------------- واجهة المستخدم (HTML/CSS) -----------------
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
    </style>
</head>
<body>
    <div class="container">
        <h1>🕌 الموسوعة الإسلامية الشاملة 📚</h1>
        <div class="search-box">
            <select id="bookSelect">
                {% for key, value in books.items() %}
                <option value="{{ key }}">{{ value }}</option>
                {% endfor %}
            </select>
            <input type="text" id="searchInput" placeholder="ابحث عن كلمة أو حديث...">
            <button onclick="doSearch()">بحث 🔍</button>
        </div>
        <div id="results"></div>
    </div>

    <script>
        async function doSearch() {
            const book = document.getElementById('bookSelect').value;
            const query = document.getElementById('searchInput').value;
            const resultsDiv = document.getElementById('results');
            
            resultsDiv.innerHTML = '<p style="text-align:center;">جاري البحث...</p>';

            const response = await fetch(`/search?book=${book}&query=${encodeURIComponent(query)}`);
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
                html += `
                    <div class="result">
                        <div class="hadith-info">
                            <span>رقم الحديث: ${item.id}</span>
                            <button class="copy-btn" onclick="copyText(this)">نسخ 📋</button>
                        </div>
                        ${item.narrator ? `<div class="narrator">${item.narrator}</div>` : ''}
                        <div class="hadith-text">${item.text}</div>
                    </div>
                `;
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
    </script>
</body>
</html>
"""

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)