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

// --- Registro ---
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

if (!registerForm.hasListener) {
  registerForm.addEventListener("submit", async function (event) {
    event.preventDefault();
    const username = document.getElementById("register-username").value.trim();
    const password = passwordInput.value.trim();
    const securityQuestion = document.getElementById("security-question").value;
    const securityAnswer = document.getElementById("security-answer").value.trim();

    feedback.style.display = "none";
    feedback.textContent = "";
    feedback.classList.remove("success", "error");

    if (!securityQuestion) {
      feedback.style.display = "block";
      feedback.classList.add("error");
      feedback.textContent = "❌ You must select a recovery question.";
      return;
    }

    if (!securityAnswer) {
      feedback.style.display = "block";
      feedback.classList.add("error");
      feedback.textContent = "❌ You must write a recovery response.";
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
        feedback.style.display = "block";
        feedback.classList.add("success");
        feedback.textContent = "✅ Registration successful. You can now log in..";
        setTimeout(() => {
          showLogin();
        }, 1500);
      } else {
        const detail = data.detail;
        feedback.style.display = "block";
        feedback.classList.add("error");
        if (Array.isArray(detail)) {
          feedback.textContent = "❌ " + detail.map((d) => d.msg || d).join(", ");
        } else {
          feedback.textContent = `❌ ${detail}`;
        }
      }
    } catch (error) {
      feedback.style.display = "block";
      feedback.classList.add("error");
      feedback.textContent = "❌ Server connection error.";
      console.error(error);
    }
  });
  registerForm.hasListener = true;
}

// --- Login ---
function setupLoginForm() {
  const loginForm = document.getElementById("login-form");
  const loginFeedback = document.getElementById("login-feedback");

  if (!loginForm.hasListener) {
    loginForm.addEventListener("submit", async function (event) {
      event.preventDefault();
      const username = document.getElementById("username").value.trim();
      const password = document.getElementById("password").value.trim();

      loginFeedback.style.display = "none";
      loginFeedback.textContent = "";
      loginFeedback.classList.remove("success", "error");

      try {
        const response = await fetch("/login", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ username, password }),
        });

        const data = await response.json();

        if (response.ok) {
          loginFeedback.style.display = "block";
          loginFeedback.classList.add("success");
          loginFeedback.textContent = `✅ Welcome ${data.user}!`;
          localStorage.setItem("user", data.user);
          setTimeout(() => {
            window.location.href = "/match-profile";
          }, 1500);
        } else {
          loginFeedback.style.display = "block";
          loginFeedback.classList.add("error");
          if (Array.isArray(data.detail)) {
            loginFeedback.textContent = "❌ Error: " + data.detail.map((e) => e.msg).join(", ");
          } else if (typeof data.detail === "string") {
            loginFeedback.textContent = `❌ Error: ${data.detail}`;
          } else {
            loginFeedback.textContent = "❌ Unknown error.";
          }
        }
      } catch (error) {
        loginFeedback.style.display = "block";
        loginFeedback.classList.add("error");
        loginFeedback.textContent = "❌ Server connection error.";
        console.error(error);
      }
    });
    loginForm.hasListener = true;
  }
}

// --- Recuperar Contraseña ---
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
    recoverFeedback.style.display = "none";

    try {
      const response = await fetch(`/recover-password?username=${username}`);
      const data = await response.json();

      if (response.ok) {
        securitySection.style.display = "block";
        securityQuestionText.textContent = data.security_question;
        securitySection.dataset.username = username;
      } else {
        recoverFeedback.style.display = "block";
        recoverFeedback.className = "feedback-message error";
        recoverFeedback.textContent = `❌ Error: ${data.detail}`;
      }
    } catch (error) {
      recoverFeedback.style.display = "block";
      recoverFeedback.className = "feedback-message error";
      recoverFeedback.textContent = "❌ Error searching for the question.";
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
        resetSection.style.display = "block";
        resetSection.dataset.username = username;
      } else {
        recoverFeedback.style.display = "block";
        recoverFeedback.className = "feedback-message error";
        recoverFeedback.textContent = `❌ Error: ${data.detail}`;
      }
    } catch (error) {
      recoverFeedback.style.display = "block";
      recoverFeedback.className = "feedback-message error";
      recoverFeedback.textContent = "❌ Error validating response.";
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

      recoverFeedback.style.display = "block";
      if (response.ok) {
        recoverFeedback.className = "feedback-message success";
        recoverFeedback.textContent = "✅ Password updated successfully.";
        setTimeout(() => showLogin(), 2000);
      } else {
        recoverFeedback.className = "feedback-message error";
        if (Array.isArray(data.detail)) {
          recoverFeedback.textContent = "❌ Error: " + data.detail.map((e) => e.msg).join(", ");
        } else if (typeof data.detail === "string") {
          recoverFeedback.textContent = `❌ Error: ${data.detail}`;
        } else {
          recoverFeedback.textContent = "❌ Unknown error.";
        }
      }
    } catch (error) {
      recoverFeedback.style.display = "block";
      recoverFeedback.className = "feedback-message error";
      recoverFeedback.textContent = "❌ Error changing password.";
    }
  });
}

// Inicializar login
setupLoginForm();

// ✅ Función global para mostrar/ocultar contraseña
function togglePasswordVisibility(id) {
  const input = document.getElementById(id);
  if (input) {
    input.type = input.type === "password" ? "text" : "password";
  }
}
