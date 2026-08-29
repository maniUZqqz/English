//
//
// const storyForm = document.getElementById("storyForm");
// const messagesDiv = document.getElementById("messages");
//
// // ذخیره کلمات وارد شده توسط کاربر
// let userWords = [];
//
// // پیام اولیه (system)
// let messages = [
//     {
//         role: "system",
//         content: "You are a helpful assistant that creates short stories including the words or topic the user gives, to help them memorize those words."
//     }
// ];
//
// storyForm.addEventListener("submit", async (e) => {
//     e.preventDefault();
//
//     const userInput = document.getElementById("userInput");
//     const userMessage = userInput.value.trim();
//     if (!userMessage) return;
//
//     // استخراج کلمات از ورودی کاربر (جدا شده با کاما یا فاصله)
//     userWords = userMessage.split(/[\s,]+/).map(word => word.trim()).filter(word => word.length > 0);
//
//     // نمایش پیام کاربر
//     addMessage(userMessage, "user-message");
//     messages.push({ role: "user", content: userMessage });
//     userInput.value = "";
//
//     // نمایش تایپینگ...
//     const typingIndicator = addMessage("typing...", "assistant-message", true);
//
//     try {
//         const response = await fetch("/chat-story", {
//             method: "POST",
//             headers: { "Content-Type": "application/json" },
//             body: JSON.stringify({ messages }),
//         });
//
//         typingIndicator.remove();
//
//         if (!response.ok) {
//             addMessage("خطایی رخ داد. لطفاً دوباره تلاش کنید.", "assistant-message");
//             return;
//         }
//
//         const data = await response.json();
//         // هایلایت کردن کلمات در داستان
//         const highlightedStory = highlightUserWords(data.content, userWords);
//         console.log("Highlighted Story:", highlightedStory); // برای بررسی
//         // نمایش پاسخ
//         addMessage(highlightedStory, "assistant-message", false, true);
//         // اضافه کردن به آرایه
//         messages.push({ role: "assistant", content: data.content });
//     } catch (err) {
//         console.error(err);
//         typingIndicator.remove();
//         addMessage("خطایی رخ داد. لطفاً دوباره تلاش کنید.", "assistant-message");
//     }
// });
//
// // تابع برای هایلایت کردن کلمات
// function highlightUserWords(text, words) {
//     if (!words || words.length === 0) return text;
//
//     // ترتیب کلمات از طول بیشتر به کمتر برای جلوگیری از تداخل
//     words.sort((a, b) => b.length - a.length);
//
//     words.forEach(word => {
//         if (word.length === 0) return;
//         // فرار کاراکترهای خاص در regex
//         const escapedWord = word.replace(/[-\/\\^$*+?.()|[\]{}]/g, '\\$&');
//         const regex = new RegExp(`\\b(${escapedWord})\\b`, 'gi');
//         text = text.replace(regex, '<span class="highlight">$1</span>');
//     });
//
//     return text;
// }
//
// function addMessage(text, className, isTemporary = false, allowHTML = false) {
//     const msgDiv = document.createElement("div");
//     msgDiv.className = `message ${className}`;
//
//     const textSpan = document.createElement("span");
//     if (allowHTML) {
//         textSpan.innerHTML = text; // استفاده از innerHTML برای نمایش HTML
//     } else {
//         textSpan.textContent = text; // استفاده از textContent برای نمایش متن ساده
//     }
//     msgDiv.appendChild(textSpan);
//
//     if (className === "assistant-message" && !isTemporary) {
//         const speakerButton = document.createElement("button");
//         speakerButton.className = "speaker-button";
//         speakerButton.innerHTML = "🔊"; // آیکون شروع
//         speakerButton.title = "پخش داستان";
//         speakerButton.dataset.isSpeaking = "false"; // حالت اولیه
//
//         // ایجاد progress bar
//         const progressContainer = document.createElement("div");
//         progressContainer.className = "progress-container";
//         const progressBar = document.createElement("div");
//         progressBar.className = "progress-bar";
//         progressContainer.appendChild(progressBar);
//
//         msgDiv.appendChild(progressContainer);
//
//         // Variables to manage speech for this message
//         let sentences = [];
//         let totalSentences = 0;
//         let currentSentenceIndex = 0;
//         let currentUtterance = null;
//
//         // Function to speak the next sentence
//         function speakNextSentence() {
//             if (currentSentenceIndex >= totalSentences) {
//                 // Finished speaking
//                 speakerButton.dataset.isSpeaking = "false";
//                 speakerButton.innerHTML = "🔊";
//                 progressBar.style.width = "100%";
//                 currentUtterance = null;
//                 return;
//             }
//
//             const sentence = sentences[currentSentenceIndex];
//             const sentenceUtterance = new SpeechSynthesisUtterance(sentence);
//             sentenceUtterance.lang = 'fa-IR';
//
//             sentenceUtterance.onstart = () => {
//                 // Update progress bar
//                 const progressPercentage = (currentSentenceIndex) / totalSentences * 100;
//                 progressBar.style.width = `${progressPercentage}%`;
//             };
//
//             sentenceUtterance.onend = () => {
//                 currentSentenceIndex++;
//                 speakNextSentence();
//             };
//
//             window.speechSynthesis.speak(sentenceUtterance);
//             currentUtterance = sentenceUtterance;
//         }
//
//         // Function to start speaking
//         function startSpeaking() {
//             // Split text into sentences
//             sentences = textSpan.textContent.match(/[^\.!\?]+[\.!\?]+/g) || [textSpan.textContent];
//             totalSentences = sentences.length;
//             currentSentenceIndex = 0;
//             speakNextSentence();
//             speakerButton.dataset.isSpeaking = "true";
//             speakerButton.innerHTML = "⏹️"; // Change icon to stop
//         }
//
//         // Function to stop speaking
//         function stopSpeaking() {
//             window.speechSynthesis.cancel();
//             speakerButton.dataset.isSpeaking = "false";
//             speakerButton.innerHTML = "🔊"; // Change icon to play
//             progressBar.style.width = "0%";
//         }
//
//         // Function to seek to a specific sentence
//         function seekToSentence(index) {
//             if (index < 0 || index >= totalSentences) return;
//             window.speechSynthesis.cancel();
//             currentSentenceIndex = index;
//             speakNextSentence();
//             // Update progress bar
//             const progressPercentage = (currentSentenceIndex) / totalSentences * 100;
//             progressBar.style.width = `${progressPercentage}%`;
//             speakerButton.dataset.isSpeaking = "true";
//             speakerButton.innerHTML = "⏹️"; // Change icon to stop
//         }
//
//         // Event listener for the speaker button
//         speakerButton.addEventListener("click", () => {
//             const isSpeaking = speakerButton.dataset.isSpeaking === "true";
//             if (!isSpeaking) {
//                 startSpeaking();
//             } else {
//                 stopSpeaking();
//             }
//         });
//
//         // Event listener for the progress bar to handle seeking
//         progressContainer.addEventListener("click", (e) => {
//             const rect = progressContainer.getBoundingClientRect();
//             const clickX = e.clientX - rect.left;
//             const width = rect.width;
//             const percentage = clickX / width;
//             const targetIndex = Math.floor(percentage * totalSentences);
//             if (speakerButton.dataset.isSpeaking === "true") {
//                 seekToSentence(targetIndex);
//             }
//         });
//
//         msgDiv.appendChild(speakerButton);
//     }
//
//     messagesDiv.appendChild(msgDiv);
//     messagesDiv.scrollTop = messagesDiv.scrollHeight;
//     if (isTemporary) {
//         return msgDiv; // برگرداندن شیء تا بعداً بتوانیم حذفش کنیم
//     }
// }



const storyForm = document.getElementById("storyForm");
const messagesDiv = document.getElementById("messages");

// ذخیره کلمات وارد شده توسط کاربر
let userWords = [];

// پیام اولیه (system)
let messages = [
    {
        role: "system",
        content: "You are a helpful assistant that creates short stories including the words or topic the user gives, to help them memorize those words."
    }
];

storyForm.addEventListener("submit", async (e) => {
    e.preventDefault();

    const userInput = document.getElementById("userInput");
    const userMessage = userInput.value.trim();
    if (!userMessage) return;

    // استخراج کلمات از ورودی کاربر (جدا شده با کاما یا فاصله)
    userWords = userMessage.split(/[\s,]+/).map(word => word.trim()).filter(word => word.length > 0);

    // نمایش پیام کاربر
    addMessage(userMessage, "user-message");
    messages.push({ role: "user", content: userMessage });
    userInput.value = "";

    // نمایش تایپینگ...
    const typingIndicator = addMessage("Creating a story...", "assistant-message", true);

    try {
        const response = await fetch("/chat-story", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ messages }),
        });

        typingIndicator.remove();

        if (!response.ok) {
            addMessage("خطایی رخ داد. لطفاً دوباره تلاش کنید.", "assistant-message");
            return;
        }

        const data = await response.json();
        // هایلایت کردن کلمات در داستان
        const highlightedStory = highlightUserWords(data.content, userWords);
        console.log("Highlighted Story:", highlightedStory); // برای بررسی
        // نمایش پاسخ
        addMessage(highlightedStory, "assistant-message", false, true);
        // اضافه کردن به آرایه
        messages.push({ role: "assistant", content: data.content });
    } catch (err) {
        console.error(err);
        typingIndicator.remove();
        addMessage("خطایی رخ داد. لطفاً دوباره تلاش کنید.", "assistant-message");
    }
});

// تابع برای هایلایت کردن کلمات
function highlightUserWords(text, words) {
    if (!words || words.length === 0) return text;

    // ترتیب کلمات از طول بیشتر به کمتر برای جلوگیری از تداخل
    words.sort((a, b) => b.length - a.length);

    words.forEach(word => {
        if (word.length === 0) return;
        // فرار کاراکترهای خاص در regex
        const escapedWord = word.replace(/[-\/\\^$*+?.()|[\]{}]/g, '\\$&');
        const regex = new RegExp(`\\b(${escapedWord})\\b`, 'gi');
        text = text.replace(regex, '<span class="highlight">$1</span>');
    });

    return text;
}

function addMessage(text, className, isTemporary = false, allowHTML = false) {
    const msgDiv = document.createElement("div");
    msgDiv.className = `message ${className}`;

    const textSpan = document.createElement("span");
    if (allowHTML) {
        textSpan.innerHTML = text; // استفاده از innerHTML برای نمایش HTML
    } else {
        textSpan.textContent = text; // استفاده از textContent برای نمایش متن ساده
    }
    msgDiv.appendChild(textSpan);

    if (className === "assistant-message" && !isTemporary) {
        // ایجاد یک کانتینر برای کنترل‌ها (دکمه و نوار پیشرفت)
        const controlsContainer = document.createElement("div");
        controlsContainer.className = "controls-container";

        const speakerButton = document.createElement("button");
        speakerButton.className = "speaker-button";
        speakerButton.innerHTML = '<i class="fas fa-volume-up"></i>'; // آیکون شروع
        speakerButton.title = "پخش داستان";
        speakerButton.dataset.isSpeaking = "false"; // حالت اولیه

        // ایجاد progress bar
        const progressContainer = document.createElement("div");
        progressContainer.className = "progress-container";
        const progressBar = document.createElement("div");
        progressBar.className = "progress-bar";
        progressContainer.appendChild(progressBar);

        // Variables to manage speech for this message
        let sentences = [];
        let totalSentences = 0;
        let currentSentenceIndex = 0;
        let isSpeaking = false;

        // Function to speak the next sentence
        function speakNextSentence() {
            if (currentSentenceIndex >= totalSentences) {
                // Finished speaking
                isSpeaking = false;
                speakerButton.dataset.isSpeaking = "false";
                speakerButton.innerHTML = '<i class="fas fa-volume-up"></i>';
                progressBar.style.width = "100%";
                return;
            }

            const sentence = sentences[currentSentenceIndex];
            const sentenceUtterance = new SpeechSynthesisUtterance(sentence);
            sentenceUtterance.lang = 'fa-IR';

            sentenceUtterance.onstart = () => {
                // Update progress bar
                const progressPercentage = (currentSentenceIndex) / totalSentences * 100;
                progressBar.style.width = `${progressPercentage}%`;
            };

            sentenceUtterance.onend = () => {
                currentSentenceIndex++;
                speakNextSentence();
            };

            window.speechSynthesis.speak(sentenceUtterance);
        }

        // Function to start speaking
        function startSpeaking() {
            // Split text into sentences
            sentences = textSpan.textContent.match(/[^.!?]+[.!?]+/g) || [textSpan.textContent];
            totalSentences = sentences.length;
            currentSentenceIndex = 0;
            isSpeaking = true;
            speakerButton.dataset.isSpeaking = "true";
            speakerButton.innerHTML = '<i class="fas fa-stop"></i>'; // Change icon to stop
            speakNextSentence();
        }

        // Function to stop speaking
        function stopSpeaking() {
            window.speechSynthesis.cancel();
            isSpeaking = false;
            speakerButton.dataset.isSpeaking = "false";
            speakerButton.innerHTML = '<i class="fas fa-volume-up"></i>'; // Change icon to play
            progressBar.style.width = "0%";
        }

        // Function to seek to a specific sentence
        function seekToSentence(index) {
            if (index < 0 || index >= totalSentences) return;
            window.speechSynthesis.cancel();
            currentSentenceIndex = index;
            if (isSpeaking) {
                speakNextSentence();
                // Update progress bar
                const progressPercentage = (currentSentenceIndex) / totalSentences * 100;
                progressBar.style.width = `${progressPercentage}%`;
            }
        }

        // Event listener برای دکمه بلندگو
        speakerButton.addEventListener("click", () => {
            const isCurrentlySpeaking = speakerButton.dataset.isSpeaking === "true";
            if (!isCurrentlySpeaking) {
                startSpeaking();
            } else {
                stopSpeaking();
            }
        });

        // Event listener برای نوار پیشرفت به منظور جابجایی
        progressContainer.addEventListener("click", (e) => {
            const rect = progressContainer.getBoundingClientRect();
            const clickX = e.clientX - rect.left;
            const width = rect.width;
            const percentage = clickX / width;
            const targetIndex = Math.floor(percentage * totalSentences);
            if (speakerButton.dataset.isSpeaking === "true") {
                seekToSentence(targetIndex);
            }
        });

        // اضافه کردن عناصر به کانتینر کنترل‌ها
        controlsContainer.appendChild(speakerButton);
        controlsContainer.appendChild(progressContainer);

        msgDiv.appendChild(controlsContainer);
    }

    messagesDiv.appendChild(msgDiv);
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
    if (isTemporary) {
        return msgDiv; // برگرداندن شیء تا بعداً بتوانیم حذفش کنیم
    }
}
