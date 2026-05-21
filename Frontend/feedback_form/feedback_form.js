const API_BASE_URL = window.BACKEND_URL || "http://127.0.0.1:8000";

const form       = document.getElementById("feedbackForm");
const statusMsg  = document.getElementById("feedbackStatus");

function setStatus(message, isError = false) {
    statusMsg.textContent   = message;
    statusMsg.style.color   = isError ? "#c52929" : "#166c38";
    statusMsg.style.display = "block";
}

form.addEventListener("submit", async (event) => {
    event.preventDefault();

    const name     = document.getElementById("name").value.trim();
    const mobile   = document.getElementById("mobile").value.trim();
    const category = document.getElementById("category").value;
    const feedback = document.getElementById("feedback").value.trim();
    const ratingEl = document.querySelector('input[name="rating"]:checked');

    if (!name || !mobile || !category || !feedback || !ratingEl) {
        setStatus("Please fill in all fields and select a rating.", true);
        return;
    }

    const rating = parseInt(ratingEl.value, 10);
    if (rating < 1 || rating > 5) {
        setStatus("Invalid rating value.", true);
        return;
    }

    const submitBtn = form.querySelector("button[type='submit']");
    submitBtn.disabled   = true;
    submitBtn.textContent = "Submitting...";
    setStatus("");

    try {
        const response = await fetch(`${API_BASE_URL}/feedback`, {
            method:  "POST",
            headers: { "Content-Type": "application/json" },
            body:    JSON.stringify({ name, mobile, category, rating, feedback }),
        });

        const result = await response.json();

        if (!response.ok) {
            setStatus(result.detail || "Could not submit feedback.", true);
            return;
        }

        setStatus(result.message || "Thank you for your feedback!");
        form.reset();
    } catch (err) {
        console.error("Feedback submission error:", err);
        setStatus("Could not connect to server. Please try again later.", true);
    } finally {
        submitBtn.disabled    = false;
        submitBtn.textContent = "Submit Feedback";
    }
});
