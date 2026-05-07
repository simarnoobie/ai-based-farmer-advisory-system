const API_BASE_URL = "http://127.0.0.1:8000";

const authStatus = document.getElementById("authStatus");
const signInForm = document.getElementById("signInForm");
const signUpForm = document.getElementById("signUpForm");
const signInTab = document.getElementById("signInTab");
const signUpTab = document.getElementById("signUpTab");

function setStatus(message, isError = false) {
    authStatus.textContent = message;
    authStatus.style.color = isError ? "#c52929" : "#166c38";
}

function switchTab(mode) {
    const isSignIn = mode === "signin";
    signInForm.classList.toggle("hidden", !isSignIn);
    signUpForm.classList.toggle("hidden", isSignIn);
    signInTab.classList.toggle("is-active", isSignIn);
    signUpTab.classList.toggle("is-active", !isSignIn);
    setStatus("");
}

function gotoQuery() {
    window.location.href = "../ai_query/query.html";
}

async function loginUser(event) {
    event.preventDefault();
    const username = document.getElementById("loginUsername").value.trim();
    const password = document.getElementById("loginPassword").value.trim();

    if (!username || !password) {
        setStatus("Please enter username and password.", true);
        return;
    }

    try {
        setStatus("Signing in...");
        const response = await fetch(`${API_BASE_URL}/login`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ username, password })
        });
        const result = await response.json();

        if (!response.ok) {
            setStatus(result.detail || "Unable to sign in.", true);
            return;
        }

        localStorage.setItem("farmer_user_id", String(result.user_id));
        localStorage.setItem("farmer_username", username);
        setStatus("Signed in successfully.");
        gotoQuery();
    } catch (err) {
        console.error(err);
        setStatus("Could not connect to server.", true);
    }
}

async function signupUser(event) {
    event.preventDefault();
    const username = document.getElementById("signupUsername").value.trim();
    const password = document.getElementById("signupPassword").value.trim();
    const confirmPassword = document.getElementById("confirmPassword").value.trim();

    if (password !== confirmPassword) {
        setStatus("Passwords do not match.", true);
        return;
    }

    try {
        setStatus("Creating account...");
        const response = await fetch(`${API_BASE_URL}/signup`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ username, password })
        });
        const result = await response.json();

        if (!response.ok) {
            setStatus(result.detail || "Unable to create account.", true);
            return;
        }

        setStatus("Account created. Please sign in.");
        switchTab("signin");
    } catch (err) {
        console.error(err);
        setStatus("Could not connect to server.", true);
    }
}

function continueAsGuest() {
    localStorage.removeItem("farmer_user_id");
    localStorage.setItem("farmer_username", "Guest");
    gotoQuery();
}