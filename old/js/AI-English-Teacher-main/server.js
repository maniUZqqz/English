const express = require('express');
const bodyParser = require('body-parser');
const axios = require('axios');

// ساخت اپ اکسپرس
const app = express();

// تنظیمات اولیه
app.use(bodyParser.json());
// سرو فایل‌های استاتیک از پوشه public
app.use(express.static('public'));

// ***** جایگزین کنید *****
const OPENAI_API_KEY = 'tpsg-xuC2QiWGfKsZWcnTRhjLLtGRXPPias9';
const OPENAI_API_BASE = 'https://api.metisai.ir/openai/v1';

// تابع کمکی برای حذف بلاک‌های کد markdown (```)
function removeMarkdownCodeBlock(str) {
    return str
        .replace(/```json/gi, '')
        .replace(/```/g, '')
        .trim();
}

/*
  1) Grammar Checker چندزبانه
  مسیر POST /api/check-grammar
*/
app.post('/api/check-grammar', async (req, res) => {
    const { text } = req.body;
    const language = 'English'; // تنظیم زبان به صورت پیش‌فرض

    if (!text) {
        return res.status(400).json({ error: 'Text is missing.' });
    }

    try {
        const response = await axios.post(
            `${OPENAI_API_BASE}/chat/completions`,
            {
                model: 'gpt-4o-mini',
                messages: [
                    {
                        role: 'system',
                        content: `
              You are a helpful assistant that checks grammar and improves sentences in English.
              Provide the corrected sentence and also explain what was wrong, if needed.
              Respond in a concise text format (no JSON needed).
            `
                    },
                    {
                        role: 'user',
                        content: "Check the grammar of this English text:\n" + text
                    }
                ],
                temperature: 0.7
            },
            {
                headers: {
                    Authorization: `Bearer ${OPENAI_API_KEY}`,
                },
            }
        );

        const reply = response.data.choices[0].message.content;
        return res.json({ result: reply });
    } catch (error) {
        console.error(error?.message || error);
        return res.status(500).json({ error: 'An error occurred while checking grammar.' });
    }
});


/*
  2) Dictionary & Translator هوشمند
  مسیر POST /api/translate
*/
app.post('/api/translate', async (req, res) => {
    const { text, sourceLang, targetLang } = req.body;
    if (!text || !sourceLang || !targetLang) {
        return res.status(400).json({ error: 'Missing text, sourceLang, or targetLang.' });
    }

    // تشخیص تک‌واژه یا جمله
    const isSingleWord = !text.includes(' ');

    // در این پرومپت به مدل می‌گوییم تنها JSON خام برگرداند
    const systemPrompt = `
    You are a helpful translation assistant.
    When the user provides text in ${sourceLang}, translate it to ${targetLang}.
    If it's a single word, also provide synonyms and antonyms in ${targetLang},
    and create an example sentence containing the original word in bold markdown like **word**.
    You must ONLY respond with a valid JSON object (no code block markers).
    The JSON must have these keys exactly: "translation", "synonyms", "antonyms", "example".
    If synonyms, antonyms, or example do not apply, set them to an empty string "".
  `;

    const userPrompt = `
    Text to translate: "${text}"
    Source language: ${sourceLang}
    Target language: ${targetLang}
    Is single word: ${isSingleWord}
  `;

    try {
        const response = await axios.post(
            `${OPENAI_API_BASE}/chat/completions`,
            {
                model: 'gpt-4o-mini', // یا gpt-4
                messages: [
                    { role: 'system', content: systemPrompt },
                    { role: 'user', content: userPrompt }
                ],
                temperature: 0.2
            },
            {
                headers: {
                    Authorization: `Bearer ${OPENAI_API_KEY}`,
                },
            }
        );

        let aiReply = response.data.choices[0].message.content;
        // پاک کردن بلاک های ```json
        aiReply = removeMarkdownCodeBlock(aiReply);

        let jsonResponse;
        try {
            jsonResponse = JSON.parse(aiReply);
        } catch (parseError) {
            console.error('AI response is not valid JSON:', aiReply);
            return res.status(500).json({ error: 'Invalid JSON from AI.' });
        }

        return res.json({
            translation: jsonResponse.translation || '',
            synonyms: jsonResponse.synonyms || '',
            antonyms: jsonResponse.antonyms || '',
            example: jsonResponse.example || ''
        });
    } catch (error) {
        console.error(error?.message || error);
        return res.status(500).json({ error: 'Translation request failed.' });
    }
});

/*
  3) Chatbot برای تقویت Writing و Reading
  مسیر POST /chat
*/
app.post('/chat', async (req, res) => {
    try {
        // در فرانت‌اند، آرایه‌ی messages را ارسال می‌کنید
        const messages = req.body.messages;

        // اولین system message را تغییر دهید تا نقش معلم Writing & Reading را داشته باشد
        // اگر کاربر قبلاً یک system message داشت، می‌توانید در فرانت‌اند آن را تغییر دهید
        // یا همینجا به ابتدای آرایه اضافه کنید:
        // (در صورتی که پیام "system" در فرانت‌اند وجود ندارد یا می‌خواهید بازنویسی کنید:)
        if (!messages.some(msg => msg.role === 'system')) {
            messages.unshift({
                role: 'system',
                content: 'You are an English teacher specialized in Writing and Reading. You help users practice and improve their skills.'
            });
        } else {
            // یا اگر می‌خواهید جایگزین کنید:
            messages[0].content = 'You are an English teacher specialized in Writing and Reading. You help users practice and improve their skills.';
        }

        // فراخوانی OpenAI
        const response = await axios.post(
            `${OPENAI_API_BASE}/chat/completions`,
            {
                model: "gpt-4o-mini", // یا gpt-4، یا هر مدل دیگری
                messages: messages,
            },
            {
                headers: {
                    Authorization: `Bearer ${OPENAI_API_KEY}`,
                    'Content-Type': 'application/json',
                },
            }
        );

        // پاسخ مدل
        res.json(response.data.choices[0].message);
    } catch (error) {
        console.error(error);
        res.status(500).json({ error: 'Something went wrong!' });
    }
});

// story creater

app.post('/chat-story', async (req, res) => {
    try {
        const messages = req.body.messages || [];

        // بررسی وجود پیام system و اضافه کردن آن در صورت عدم وجود
        if (!messages.some(msg => msg.role === 'system')) {
            messages.unshift({
                role: 'system',
                content: 'You are a helpful assistant that creates short very simple stories including the words or topic the user gives, to help them memorize those words.'
            });
        }

        const response = await axios.post(
            `${OPENAI_API_BASE}/chat/completions`,
            {
                model: 'gpt-4o-mini', // اطمینان حاصل کنید که مدل صحیح را انتخاب کرده‌اید
                messages: messages,
            },
            {
                headers: {
                    Authorization: `Bearer ${OPENAI_API_KEY}`,
                    'Content-Type': 'application/json',
                },
            }
        );

        // ارسال پاسخ مدل به فرانت‌اند
        res.json(response.data.choices[0].message);
    } catch (error) {
        console.error('Error in /chat-story:', error.response?.data || error.message || error);
        res.status(500).json({ error: 'Failed to generate story.' });
    }
});

// مسیر POST /voice-chat
app.post('/voice-chat', async (req, res) => {
    try {
        const { message } = req.body;

        // بررسی اینکه آیا پیام ارسال شده است یا خیر
        if (!message) {
            return res.status(400).json({ error: 'Message is missing.' });
        }

        // تعریف پیام سیستم برای چت‌بات عمومی
        const systemPrompt = 'You are an experienced and specialized English teacher focused on conversation practice. Your role is to help users improve their English speaking skills through interactive and natural dialogues. You are capable of understanding all English accents and dialects and provide responses that are fluent, accurate, and appropriate to the user\'s language level. If the user communicates in a language other than English, you politely ask them to continue in English. You use gentle corrections and constructive feedback to enhance the user\'s speech, avoiding confusion or getting stuck in the conversation. Additionally, you create a friendly and encouraging environment to help users speak with greater confidence.\n';
        // ارسال درخواست به OpenAI
        const response = await axios.post(
            `${OPENAI_API_BASE}/chat/completions`,
            {
                model: 'gpt-4o-mini', // اطمینان حاصل کنید که مدل صحیح را انتخاب کرده‌اید
                messages: [
                    { role: 'system', content: systemPrompt },
                    { role: 'user', content: message }
                ],
                temperature: 0.7,
                max_tokens: 1500, // تنظیم حداکثر تعداد توکن‌های پاسخ
                n: 1,
                stop: null
            },
            {
                headers: {
                    Authorization: `Bearer ${OPENAI_API_KEY}`,
                    'Content-Type': 'application/json',
                },
            }
        );

        // دریافت پاسخ از OpenAI
        const assistantMessage = response.data.choices[0].message.content;

        // ارسال پاسخ به فرانت‌اند
        res.json({ reply: assistantMessage });
    } catch (error) {
        console.error('Error in /voice-chat:', error.response?.data || error.message || error);
        res.status(500).json({ error: 'Failed to process voice chat.' });
    }
});





// راه‌اندازی سرور
const PORT = process.env.PORT || 3013;
app.listen(PORT, () => {
    console.log(`Server is running on http://localhost:${PORT}`);
});