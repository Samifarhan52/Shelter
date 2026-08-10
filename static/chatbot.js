/**
 * 🤖 SHELTER HUNT AI ASSISTANT FRONTEND ENGINE
 * Provides interactive chat UI, quick response actions, lead capture & website guidance.
 */

document.addEventListener('DOMContentLoaded', function() {
    const trigger = document.getElementById('sh-chatbot-trigger');
    const windowEl = document.getElementById('sh-chat-window');
    const closeBtn = document.getElementById('sh-chat-close-btn');
    const bodyEl = document.getElementById('sh-chat-body');
    const inputEl = document.getElementById('sh-chat-input');
    const sendBtn = document.getElementById('sh-chat-send-btn');
    const tooltip = document.getElementById('sh-ai-buddy-tooltip');
    const tooltipClose = document.getElementById('sh-ai-buddy-tooltip-close');

    if (!trigger || !windowEl || !bodyEl || !inputEl || !sendBtn) return;

    let isWaitingForResponse = false;
    let hasSentInitialWelcome = false;

    // Toggle Chat Window
    function toggleChatWindow() {
        const isActive = windowEl.classList.contains('active');
        if (isActive) {
            windowEl.classList.remove('active');
        } else {
            windowEl.classList.add('active');
            if (tooltip) tooltip.style.display = 'none'; // Hide tooltip when chat opens
            if (!hasSentInitialWelcome) {
                renderInitialWelcome();
                hasSentInitialWelcome = true;
            }
            setTimeout(() => inputEl.focus(), 300);
        }
    }

    trigger.addEventListener('click', toggleChatWindow);
    if (closeBtn) closeBtn.addEventListener('click', toggleChatWindow);

    // Dismiss Tooltip
    if (tooltipClose) {
        tooltipClose.addEventListener('click', function(e) {
            e.stopPropagation();
            if (tooltip) tooltip.style.display = 'none';
        });
    }

    if (tooltip) {
        tooltip.addEventListener('click', function(e) {
            if (e.target !== tooltipClose) {
                toggleChatWindow();
            }
        });
    }

    // Helper: Scroll to bottom
    function scrollToBottom() {
        bodyEl.scrollTop = bodyEl.scrollHeight;
    }

    // Helper: Get Current Time String
    function getTimeStr() {
        const now = new Date();
        return now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    }

    // Render User Message
    function appendUserMessage(text) {
        const msgDiv = document.createElement('div');
        msgDiv.className = 'sh-msg sh-msg-user';
        msgDiv.innerHTML = `
            <div class="sh-msg-bubble">${escapeHtml(text)}</div>
            <div class="sh-msg-time">${getTimeStr()}</div>
        `;
        bodyEl.appendChild(msgDiv);
        scrollToBottom();
    }

    // Render AI Message with optional action buttons & inline lead form trigger
    function appendAIMessage(htmlContent, actionChips = [], showLeadForm = false) {
        const msgDiv = document.createElement('div');
        msgDiv.className = 'sh-msg sh-msg-ai';
        
        let chipsHtml = '';
        if (actionChips && actionChips.length > 0) {
            chipsHtml = '<div class="sh-action-chips">';
            actionChips.forEach(chip => {
                if (chip.url) {
                    const isExternal = chip.url.startsWith('http');
                    chipsHtml += `<a href="${chip.url}" ${isExternal ? 'target="_blank" rel="noopener noreferrer"' : ''} class="sh-chip-btn ${chip.isPrimary ? 'gold-filled' : ''}">${chip.icon ? chip.icon + ' ' : ''}${escapeHtml(chip.label)}</a>`;
                } else if (chip.action === 'lead_form') {
                    chipsHtml += `<button class="sh-chip-btn gold-filled sh-trigger-lead-btn">${chip.icon ? chip.icon + ' ' : ''}${escapeHtml(chip.label)}</button>`;
                } else {
                    chipsHtml += `<button class="sh-chip-btn sh-text-chip-btn" data-query="${escapeHtml(chip.label)}">${chip.icon ? chip.icon + ' ' : ''}${escapeHtml(chip.label)}</button>`;
                }
            });
            chipsHtml += '</div>';
        }

        let formHtml = '';
        if (showLeadForm) {
            formHtml = `
                <div class="sh-inline-lead-card">
                    <h6>📞 Request Expert Callback</h6>
                    <form class="sh-lead-form">
                        <input type="text" class="form-control sh-lead-name" placeholder="Your Full Name *" required>
                        <input type="tel" class="form-control sh-lead-phone" placeholder="10-digit Mobile Number *" required pattern="[0-9]{10}">
                        <input type="email" class="form-control sh-lead-email" placeholder="Email Address (Optional)">
                        <button type="submit" class="btn-submit-lead">Request Callback Now 💬</button>
                    </form>
                </div>
            `;
        }

        msgDiv.innerHTML = `
            <div class="sh-msg-bubble">
                <div>${htmlContent}</div>
                ${chipsHtml}
                ${formHtml}
            </div>
            <div class="sh-msg-time">${getTimeStr()}</div>
        `;

        bodyEl.appendChild(msgDiv);
        scrollToBottom();

        // Bind text chip clicks
        msgDiv.querySelectorAll('.sh-text-chip-btn').forEach(btn => {
            btn.addEventListener('click', function() {
                const query = this.getAttribute('data-query');
                if (query) handleUserSend(query);
            });
        });

        // Bind lead trigger button clicks
        msgDiv.querySelectorAll('.sh-trigger-lead-btn').forEach(btn => {
            btn.addEventListener('click', function() {
                appendAIMessage("Please fill out your contact details below so our advisory team can connect with you:", [], true);
            });
        });

        // Bind inline lead form submit
        const leadForm = msgDiv.querySelector('.sh-lead-form');
        if (leadForm) {
            leadForm.addEventListener('submit', function(e) {
                e.preventDefault();
                submitInlineLead(this, msgDiv);
            });
        }
    }

    // Render Typing Indicator
    function showTypingIndicator() {
        const msgDiv = document.createElement('div');
        msgDiv.className = 'sh-msg sh-msg-ai sh-typing-indicator-msg';
        msgDiv.innerHTML = `
            <div class="sh-msg-bubble" style="padding: 8px 12px;">
                <div class="sh-typing-dots">
                    <span></span><span></span><span></span>
                </div>
            </div>
        `;
        bodyEl.appendChild(msgDiv);
        scrollToBottom();
        return msgDiv;
    }

    function removeTypingIndicator(indicatorEl) {
        if (indicatorEl && indicatorEl.parentNode) {
            indicatorEl.parentNode.removeChild(indicatorEl);
        }
    }

    // Initial Welcome Message
    function renderInitialWelcome() {
        const welcomeText = "Hello! 👋 I'm your **Shelter Hunt AI Assistant**. How can I assist you with your property advisory today?";
        const welcomeChips = [
            { label: "What services do you provide?", icon: "💼" },
            { label: "Tell me about available properties", icon: "🏙️" },
            { label: "Book a Strategy Session", icon: "📅", url: "/book-session", isPrimary: true },
            { label: "Contact Us", icon: "📞", action: "lead_form" }
        ];
        appendAIMessage(formatMarkdown(welcomeText), welcomeChips);
    }

    // Handle User Send Message
    function handleUserSend(overrideText = null) {
        const text = (overrideText || inputEl.value).trim();
        if (!text || isWaitingForResponse) return;

        if (!overrideText) inputEl.value = '';
        appendUserMessage(text);

        isWaitingForResponse = true;
        sendBtn.disabled = true;
        const typingEl = showTypingIndicator();

        fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: text })
        })
        .then(res => res.json())
        .then(data => {
            removeTypingIndicator(typingEl);
            isWaitingForResponse = false;
            sendBtn.disabled = false;

            if (data.success) {
                appendAIMessage(
                    formatMarkdown(data.response),
                    data.action_chips || [],
                    data.show_lead_form || false
                );
            } else {
                appendAIMessage(
                    "I'm having a brief connection glitch. Feel free to connect directly with our expert team!",
                    [
                        { label: "Book Strategy Session", url: "/book-session", isPrimary: true },
                        { label: "Request Callback", action: "lead_form" }
                    ]
                );
            }
        })
        .catch(err => {
            console.error("Chat API error:", err);
            removeTypingIndicator(typingEl);
            isWaitingForResponse = false;
            sendBtn.disabled = false;

            appendAIMessage(
                "Unable to connect right now. You can reach out to us directly at **+91 8050749331** or book a strategy session.",
                [
                    { label: "Book Strategy Session", url: "/book-session", isPrimary: true },
                    { label: "Request Callback", action: "lead_form" }
                ]
            );
        });
    }

    // Handle Inline Lead Form Submission
    function submitInlineLead(formEl, msgDiv) {
        const nameInput = formEl.querySelector('.sh-lead-name');
        const phoneInput = formEl.querySelector('.sh-lead-phone');
        const emailInput = formEl.querySelector('.sh-lead-email');
        const submitBtn = formEl.querySelector('.btn-submit-lead');

        const name = nameInput.value.trim();
        const phone = phoneInput.value.replace(/\D/g, '');
        const email = emailInput.value.trim();

        if (!name || phone.length !== 10) {
            alert('Please provide your full name and a valid 10-digit mobile number.');
            return;
        }

        submitBtn.disabled = true;
        submitBtn.innerText = "Submitting...";

        const formData = new FormData();
        formData.append('full_name', name);
        formData.append('phone', phone);
        formData.append('email', email);

        fetch('/submit-quick-lead', {
            method: 'POST',
            body: formData
        })
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                // Replace card content with success message
                const card = formEl.closest('.sh-inline-lead-card');
                if (card) {
                    card.innerHTML = `
                        <div style="color: #10b981; font-weight: 800; font-size: 0.88rem; margin-bottom: 6px;">
                            ✅ Callback Request Received!
                        </div>
                        <p style="font-size: 0.82rem; color: #475569; margin-bottom: 10px;">
                            Thank you, <strong>${escapeHtml(name)}</strong>. Our property consultant will get in touch with you shortly.
                        </p>
                        ${data.whatsapp_url ? `<a href="${data.whatsapp_url}" target="_blank" class="sh-chip-btn gold-filled" style="width: 100%; justify-content: center;">Chat on WhatsApp 💬</a>` : ''}
                    `;
                }
            } else {
                alert(data.message || 'Error submitting lead. Please try again.');
                submitBtn.disabled = false;
                submitBtn.innerText = "Request Callback Now 💬";
            }
        })
        .catch(err => {
            console.error("Lead submission error:", err);
            alert('Connection error. Please try again.');
            submitBtn.disabled = false;
            submitBtn.innerText = "Request Callback Now 💬";
        });
    }

    // Input Listeners
    sendBtn.addEventListener('click', () => handleUserSend());
    inputEl.addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            e.preventDefault();
            handleUserSend();
        }
    });

    // Helper Utilities
    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    function formatMarkdown(text) {
        if (!text) return '';
        let html = escapeHtml(text);
        // Bold formatting **text**
        html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
        // Links [label](url)
        html = html.replace(/\[(.*?)\]\((.*?)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer" style="color: #d4af37; text-decoration: underline; font-weight: 700;">$1</a>');
        // Bullet lists
        html = html.replace(/\n• (.*?)(?=\n|$)/g, '<br>• $1');
        html = html.replace(/\n\n/g, '<br><br>');
        return html;
    }
});
