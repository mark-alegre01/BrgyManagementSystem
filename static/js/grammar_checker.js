/**
 * Grammar Checker helper for Barangay Management System
 * Uses LanguageTool Free API (Public)
 */
const GrammarChecker = {
    async check(text) {
        if (!text || text.length < 5) return null;

        try {
            const response = await fetch('https://api.languagetool.org/v2/check', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded'
                },
                body: new URLSearchParams({
                    'text': text,
                    'language': 'en-US'
                })
            });

            if (!response.ok) return null;
            const data = await response.json();
            return data.matches;
        } catch (error) {
            console.error('Grammar check failed:', error);
            return null;
        }
    },

    init(textareaId, feedbackId) {
        const textarea = document.getElementById(textareaId);
        const feedback = document.getElementById(feedbackId);
        if (!textarea || !feedback) return;

        let timeout = null;
        textarea.addEventListener('input', () => {
            clearTimeout(timeout);
            feedback.innerHTML = '<span style="color: #64748b; font-size: 12px;"><i class="fas fa-spinner fa-spin"></i> Checking grammar...</span>';

            timeout = setTimeout(async () => {
                const results = await this.check(textarea.value);
                if (results && results.length > 0) {
                    let html = '<div style="color: #ef4444; font-size: 12px; margin-top: 8px; background: #fef2f2; padding: 10px; border-radius: 8px; border: 1px solid #fee2e2;">';
                    html += '<strong style="display: block; margin-bottom: 4px;"><i class="fas fa-exclamation-circle"></i> Grammar Suggestions:</strong>';
                    results.slice(0, 3).forEach(match => {
                        html += `<div style="margin-bottom: 4px;">• "${match.context.text.substr(match.context.offset, match.context.length)}" - ${match.message}</div>`;
                    });
                    html += '</div>';
                    feedback.innerHTML = html;
                } else {
                    feedback.innerHTML = '<span style="color: #10b981; font-size: 12px;"><i class="fas fa-check-circle"></i> Looks good!</span>';
                }
            }, 1500);
        });
    }
};

window.GrammarChecker = GrammarChecker;
