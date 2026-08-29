// انتخاب المان‌ها از DOM
const sourceLangSelect = document.getElementById('sourceLang');
const targetLangSelect = document.getElementById('targetLang');
const sourceTextArea = document.getElementById('sourceText');
const translatedTextArea = document.getElementById('translatedText');

const translateBtn = document.getElementById('translateBtn');
const micBtn = document.getElementById('micBtn');
const speakSourceBtn = document.getElementById('speakSourceBtn');
const speakTargetBtn = document.getElementById('speakTargetBtn');

const dictionaryResult = document.getElementById('dictionaryResult');
const synonymsSpan = document.getElementById('synonyms');
const antonymsSpan = document.getElementById('antonyms');
const exampleSpan = document.getElementById('exampleSentence');

// 1) دکمه‌ی ضبط صدا (ورودی کاربر)
let recognition;
if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
    // برای سازگاری با مرورگرهای مختلف
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    recognition = new SpeechRecognition();
    recognition.lang = 'en-US'; // به صورت پیشفرض. یا بسته به زبان sourceLangSelect
}

micBtn.addEventListener('click', () => {
    if (!recognition) {
        alert('Your browser does not support Speech Recognition');
        return;
    }
    recognition.lang = mapLanguageToLocale(sourceLangSelect.value);
    recognition.start();
});

// وقتی صدا شناسایی شد و تبدیل به متن شد
if (recognition) {
    recognition.onresult = (event) => {
        const transcript = event.results[0][0].transcript;
        sourceTextArea.value = transcript;
    };
}

// یک تابع کمکی برای تعیین locale مرورگر، بر اساس زبان انتخاب شده
function mapLanguageToLocale(lang) {
    switch (lang) {
        case 'English': return 'en-US';
        case 'French':  return 'fr-FR';
        case 'German':  return 'de-DE';
        case 'Persian': return 'fa-IR';
        case 'Spanish': return 'es-ES';
        default:        return 'en-US';
    }
}

// 2) تبدیل متن به گفتار
function speakText(text, lang) {
    if ('speechSynthesis' in window) {
        const utterance = new SpeechSynthesisUtterance(text);
        utterance.lang = mapLanguageToLocale(lang);
        speechSynthesis.speak(utterance);
    } else {
        alert('Your browser does not support Text To Speech');
    }
}

speakSourceBtn.addEventListener('click', () => {
    speakText(sourceTextArea.value, sourceLangSelect.value);
});

speakTargetBtn.addEventListener('click', () => {
    speakText(translatedTextArea.value, targetLangSelect.value);
});

// 3) ترجمه با هوش مصنوعی
translateBtn.addEventListener('click', async () => {
    const text = sourceTextArea.value.trim();
    const sourceLang = sourceLangSelect.value;
    const targetLang = targetLangSelect.value;

    if (!text) {
        alert('Please enter or speak some text to translate.');
        return;
    }

    try {
        const response = await fetch('/api/translate', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                text,
                sourceLang,
                targetLang
            }),
        });

        if (!response.ok) throw new Error('Translation failed.');

        const data = await response.json();

        // داده‌ی دریافتی را در textarea مقصد نمایش می‌دهیم
        translatedTextArea.value = data.translation || '';

        // اگر مترادف و متضاد و جمله نمونه فرستاد، نمایش می‌دهیم
        if (data.synonyms || data.antonyms || data.example) {
            dictionaryResult.classList.remove('hidden');
            synonymsSpan.textContent = data.synonyms || 'N/A';
            antonymsSpan.textContent = data.antonyms || 'N/A';
            exampleSpan.innerHTML = data.example || 'N/A';  // ممکن است شامل تگ‌های HTML برای Bold کردن باشد
        } else {
            dictionaryResult.classList.add('hidden');
        }
    } catch (error) {
        console.error(error);
        alert('Error while translating. Check console for details.');
    }
});
