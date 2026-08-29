document.getElementById('grammarForm').addEventListener('submit', async (e) => {
    e.preventDefault();

    const inputText = document.getElementById('inputText').value.trim();
    const selectedLanguage = 'English'; // تنظیم زبان به صورت پیش‌فرض به انگلیسی

    if (!inputText) {
        alert('Please enter some text.');
        return;
    }

    // نمایش پیام کاربر
    addMessage(inputText, 'user-message');

    // ارسال درخواست به سرور
    try {
        const response = await fetch('/api/check-grammar', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                text: inputText,
                language: selectedLanguage, // ارسال زبان به صورت پیش‌فرض
            }),
        });

        if (!response.ok) throw new Error('Failed to fetch');

        const data = await response.json();
        addMessage(data.result, 'assistant-message');
    } catch (error) {
        alert('An error occurred. Please try again.');
        console.error(error);
        addMessage('An error occurred while checking grammar. Please try again.', 'assistant-message');
    }

    // پاک کردن textarea
    document.getElementById('inputText').value = '';
});

/**
 * افزودن پیام به صفحه
 * @param {string} text - متن پیام
 * @param {string} className - کلاس CSS (user-message یا assistant-message)
 */
function addMessage(text, className) {
    const messagesDiv = document.getElementById('messages');
    const messageDiv = document.createElement('div');
    messageDiv.classList.add('message', className);
    messageDiv.textContent = text;
    messagesDiv.appendChild(messageDiv);
    messagesDiv.scrollTop = messagesDiv.scrollHeight;

    // حذف کد مربوط به resultBox
    /*
    if (className === 'assistant-message') {
        const resultBox = document.getElementById('resultBox');
        const resultText = document.getElementById('resultText');
        if (resultBox && resultText) {
            resultBox.classList.add('visible');
            resultText.textContent = text;
        }
    }
    */
}
