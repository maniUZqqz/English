document.addEventListener("DOMContentLoaded", () => {
    const chatForm = document.getElementById("chatForm");
    const messagesDiv = document.getElementById("messages");
    const userInput = document.getElementById("userInput");

    let messages = [
        { role: "system", content: "شما یک دستیار مفید هستید." }
    ];

    chatForm.addEventListener("submit", async (e) => {
        e.preventDefault();

        const userMessage = userInput.value.trim();
        if (!userMessage) return;

        addMessage(userMessage, "user-message");
        messages.push({ role: "user", content: userMessage });
        userInput.value = "";

        const typingIndicator = addMessage("typing...", "assistant-message", true);

        try {
            const response = await fetch("/chat", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify({ messages }),
            });

            if (!response.ok) {
                throw new Error("Error conecting server...");
            }

            const data = await response.json();
            typingIndicator.remove();
            addMessage(data.content, "assistant-message");
            messages.push({ role: "assistant", content: data.content });
        } catch (error) {
            typingIndicator.remove();
            addMessage("متاسفانه مشکلی پیش آمد. لطفا دوباره تلاش کنید.", "assistant-message");
            console.error(error);
        }
    });

    function addMessage(content, className, isTemporary = false) {
        const messageDiv = document.createElement("div");
        messageDiv.className = `message ${className}`;

        // افزودن آواتار
        if (className.includes("assistant")) {
            const avatar = document.createElement("img");
            avatar.src = "assistant-avatar.png"; // مسیر آواتار دستیار
            avatar.alt = "🤖";
            avatar.className = "avatar";
            messageDiv.appendChild(avatar);
        } else if (className.includes("user")) {
            const avatar = document.createElement("img");
            avatar.src = "user-avatar.png"; // مسیر آواتار کاربر
            avatar.alt = "👤";
            avatar.className = "avatar";
            messageDiv.appendChild(avatar);
        }

        const text = document.createElement("span");
        text.textContent = content;
        messageDiv.appendChild(text);

        messagesDiv.appendChild(messageDiv);
        messagesDiv.scrollTop = messagesDiv.scrollHeight;

        if (isTemporary) return messageDiv;
    }

    // ایجاد ستاره‌های تصادفی
    function createStars(count) {
        const starsContainer = document.querySelector(".stars");
        for (let i = 0; i < count; i++) {
            const star = document.createElement("div");
            star.classList.add("star");
            star.style.top = `${Math.random() * 100}%`;
            star.style.left = `${Math.random() * 100}%`;
            star.style.animationDuration = `${Math.random() * 5 + 5}s`;
            star.style.animationDelay = `${Math.random() * 5}s`;
            starsContainer.appendChild(star);
        }
    }

    createStars(100); // ایجاد 100 ستاره
});
