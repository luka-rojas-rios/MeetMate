function showLogin() {
  document.getElementById("welcome-screen").style.display = "none";
  document.getElementById("login-container").style.display = "block";
  document.getElementById("register-container").style.display = "none";
  if (document.getElementById("recover-container")) {
    document.getElementById("recover-container").style.display = "none";
  }
}

function showRegister() {
  document.getElementById("welcome-screen").style.display = "none";
  document.getElementById("login-container").style.display = "none";
  document.getElementById("register-container").style.display = "block";
  if (document.getElementById("recover-container")) {
    document.getElementById("recover-container").style.display = "none";
  }
}

const registerForm = document.getElementById("register-form");
const feedback = document.getElementById("register-feedback");
const passwordInput = document.getElementById("register-password");

passwordInput.addEventListener("input", () => {
  const password = passwordInput.value;
  document.getElementById("rule-length").className = password.length >= 6 ? "valid" : "invalid";
  document.getElementById("rule-uppercase").className = /[A-Z]/.test(password) ? "valid" : "invalid";
  document.getElementById("rule-lowercase").className = /[a-z]/.test(password) ? "valid" : "invalid";
  document.getElementById("rule-number").className = /[0-9]/.test(password) ? "valid" : "invalid";
  document.getElementById("rule-special").className = /[\W_]/.test(password) ? "valid" : "invalid";
});

function showFeedback(el, type, text) {
  el.className = "flash " + type;
  el.style.display = "block";
  el.textContent = text;
}

function clearFeedback(el) {
  el.style.display = "none";
  el.textContent = "";
  el.className = "flash";
}

registerForm.addEventListener("submit", async function (event) {
  event.preventDefault();
  const username = document.getElementById("register-username").value.trim();
  const password = passwordInput.value.trim();
  const securityQuestion = document.getElementById("security-question").value;
  const securityAnswer = document.getElementById("security-answer").value.trim();

  clearFeedback(feedback);

  if (!securityQuestion) {
    showFeedback(feedback, "error", "You must select a recovery question.");
    return;
  }

  if (!securityAnswer) {
    showFeedback(feedback, "error", "Please write a recovery answer.");
    return;
  }

  try {
    const response = await fetch("/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        username,
        password,
        security_question: securityQuestion,
        security_answer: securityAnswer,
      }),
    });

    const data = await response.json();

    if (response.ok) {
      showFeedback(feedback, "success", "Registration successful. You can now log in.");
      setTimeout(showLogin, 1500);
    } else {
      const detail = data.detail;
      const text = Array.isArray(detail) ? detail.map((d) => d.msg || d).join(", ") : detail;
      showFeedback(feedback, "error", text);
    }
  } catch (error) {
    showFeedback(feedback, "error", "Server connection error.");
    console.error(error);
  }
});

function setupLoginForm() {
  const loginForm = document.getElementById("login-form");
  const loginFeedback = document.getElementById("login-feedback");

  loginForm.addEventListener("submit", async function (event) {
    event.preventDefault();
    const username = document.getElementById("username").value.trim();
    const password = document.getElementById("password").value.trim();

    clearFeedback(loginFeedback);

    try {
      const response = await fetch("/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      });

      const data = await response.json();

      if (response.ok) {
        showFeedback(loginFeedback, "success", `Welcome, ${data.user}`);
        localStorage.setItem("user", data.user);
        setTimeout(() => { window.location.href = "/dashboard"; }, 1200);
      } else {
        const text = Array.isArray(data.detail)
          ? data.detail.map((e) => e.msg).join(", ")
          : (typeof data.detail === "string" ? data.detail : "Unknown error.");
        showFeedback(loginFeedback, "error", text);
      }
    } catch (error) {
      showFeedback(loginFeedback, "error", "Server connection error.");
      console.error(error);
    }
  });
}

function showRecoverPassword() {
  document.getElementById("welcome-screen").style.display = "none";
  document.getElementById("login-container").style.display = "none";
  document.getElementById("register-container").style.display = "none";
  document.getElementById("recover-container").style.display = "block";

  const recoverForm = document.getElementById("recover-form");
  const securitySection = document.getElementById("security-question-section");
  const resetSection = document.getElementById("reset-password-section");
  const securityQuestionText = document.getElementById("security-question-text");
  const recoverFeedback = document.getElementById("recover-feedback");

  recoverForm.addEventListener("submit", async function (event) {
    event.preventDefault();
    const username = document.getElementById("recover-username").value.trim();
    clearFeedback(recoverFeedback);

    try {
      const response = await fetch(`/recover-password?username=${username}`);
      const data = await response.json();

      if (response.ok) {
        securitySection.style.display = "grid";
        securityQuestionText.textContent = data.security_question;
        securitySection.dataset.username = username;
      } else {
        showFeedback(recoverFeedback, "error", data.detail);
      }
    } catch (error) {
      showFeedback(recoverFeedback, "error", "Error searching for the question.");
    }
  });

  document.getElementById("validate-answer-button").addEventListener("click", async function () {
    const username = securitySection.dataset.username;
    const answer = document.getElementById("security-answer-input").value.trim();

    try {
      const response = await fetch("/validate-answer", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, security_answer: answer }),
      });
      const data = await response.json();

      if (response.ok) {
        resetSection.style.display = "grid";
        resetSection.dataset.username = username;
      } else {
        showFeedback(recoverFeedback, "error", data.detail);
      }
    } catch (error) {
      showFeedback(recoverFeedback, "error", "Error validating answer.");
    }
  });

  document.getElementById("reset-password-button").addEventListener("click", async function () {
    const username = resetSection.dataset.username;
    const newPassword = document.getElementById("new-password").value.trim();

    try {
      const response = await fetch("/reset-password", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, new_password: newPassword }),
      });
      const data = await response.json();

      if (response.ok) {
        showFeedback(recoverFeedback, "success", "Password updated successfully.");
        setTimeout(showLogin, 1500);
      } else {
        const text = Array.isArray(data.detail)
          ? data.detail.map((e) => e.msg).join(", ")
          : (typeof data.detail === "string" ? data.detail : "Unknown error.");
        showFeedback(recoverFeedback, "error", text);
      }
    } catch (error) {
      showFeedback(recoverFeedback, "error", "Error changing password.");
    }
  });
}

setupLoginForm();

function togglePasswordVisibility(id, button) {
  const input = document.getElementById(id);
  if (!input) return;
  const showing = input.type === "password";
  input.type = showing ? "text" : "password";
  if (button) button.textContent = showing ? "Hide" : "Show";
}
