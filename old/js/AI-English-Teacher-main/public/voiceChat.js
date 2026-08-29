const startVoiceButton = document.getElementById("startVoiceButton");
const stopVoiceButton = document.getElementById("stopVoiceButton");
const voiceMessagesDiv = document.getElementById("voiceMessages");
const statusText = document.getElementById("statusText");

let recognition;
let isListening = false;

// بررسی پشتیبانی مرورگر از Web Speech API
if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
    alert("مرورگر شما از Web Speech API پشتیبانی نمی‌کند.");
} else {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    recognition = new SpeechRecognition();
    recognition.lang = 'fa-IR'; // تنظیم زبان به فارسی
    recognition.interimResults = true; // فعال‌سازی نتایج موقتی
    recognition.maxAlternatives = 3; // افزایش تعداد گزینه‌ها
    recognition.continuous = true; // فعال‌سازی حالت پیوسته

    recognition.onstart = () => {
        isListening = true;
        startVoiceButton.disabled = true;
        stopVoiceButton.disabled = false;
        startVoiceButton.classList.add('active');
        statusText.textContent = "در حال ضبط...";
    };

    recognition.onresult = (event) => {
        let finalTranscript = '';
        for (let i = event.resultIndex; i < event.results.length; ++i) {
            if (event.results[i].isFinal) {
                const transcript = event.results[i][0].transcript.trim();
                finalTranscript += transcript + ' ';
                addVoiceMessage(transcript, 'user-voice-message', 'user');
                sendVoiceMessage(transcript);
            }
        }
    };

    recognition.onerror = (event) => {
        console.error('Speech recognition error:', event.error);
        isListening = false;
        startVoiceButton.disabled = false;
        stopVoiceButton.disabled = true;
        startVoiceButton.classList.remove('active');
        statusText.textContent = "آماده برای ضبط";
        alert("خطا در شناسایی گفتار رخ داد.");
    };

    recognition.onend = () => {
        isListening = false;
        startVoiceButton.disabled = false;
        stopVoiceButton.disabled = true;
        startVoiceButton.classList.remove('active');
        statusText.textContent = "آماده برای ضبط";
    };
}

startVoiceButton.addEventListener("click", () => {
    if (!isListening) {
        recognition.start();
    }
});

stopVoiceButton.addEventListener("click", () => {
    if (isListening) {
        recognition.stop();
    }
});

async function sendVoiceMessage(text) {
    try {
        const response = await fetch("/voice-chat", { // تغییر مسیر به /voice-chat
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ message: text }), // تغییر ساختار داده به { message: text }
        });

        if (!response.ok) {
            addVoiceMessage("خطایی رخ داد. لطفاً دوباره تلاش کنید.", 'assistant-voice-message', 'assistant');
            return;
        }

        const data = await response.json();
        addVoiceMessage(data.reply, 'assistant-voice-message', 'assistant'); // تغییر data.content به data.reply
        speakText(data.reply); // تغییر data.content به data.reply
    } catch (err) {
        console.error(err);
        addVoiceMessage("خطایی رخ داد. لطفاً دوباره تلاش کنید.", 'assistant-voice-message', 'assistant');
    }
}

function addVoiceMessage(text, className, sender) {
    const msgDiv = document.createElement("div");
    msgDiv.className = `voice-message ${className}`;

    const avatarDiv = document.createElement("div");
    avatarDiv.className = `avatar ${sender === 'user' ? 'avatar-user' : 'avatar-assistant'}`;
    avatarDiv.textContent = sender === 'user' ? '👤' : '🤖';

    const textSpan = document.createElement("span");
    textSpan.textContent = text;

    msgDiv.appendChild(avatarDiv);
    msgDiv.appendChild(textSpan);

    voiceMessagesDiv.appendChild(msgDiv);
    voiceMessagesDiv.scrollTop = voiceMessagesDiv.scrollHeight;
}

function speakText(text) {
    if ('speechSynthesis' in window) {
        const utterance = new SpeechSynthesisUtterance(text);
        utterance.lang = 'fa-IR'; // تنظیم زبان به فارسی
        window.speechSynthesis.speak(utterance);
    } else {
        alert("مرورگر شما از قابلیت تبدیل متن به گفتار پشتیبانی نمی‌کند.");
    }
}
