document.getElementById("loginForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const btn = document.getElementById("submitBtn");
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner" style="border-color:rgba(255,255,255,0.3);border-top-color:white"></span>';

  const payload = {
    email: document.getElementById("email").value.trim(),
    password: document.getElementById("password").value,
  };
  try {
    const data = await apiFetch("/api/auth/login", { method: "POST", body: payload, auth: false });
    saveSession(data.access_token, data.user);
    toast("Welcome back, " + data.user.name, "success", 1500);
    setTimeout(() => window.location.href = "../dashboard/dashboard.html", 500);
  } catch (err) {
    toast(err.message, "error");
    btn.disabled = false;
    btn.textContent = "Sign in";
  }
});

const forgotPasswordBtn = document.getElementById("forgotPasswordBtn");
const closeResetBtn = document.getElementById("closeResetBtn");
const resetPanel = document.getElementById("resetPanel");

forgotPasswordBtn.addEventListener("click", () => {
  document.getElementById("resetEmail").value = document.getElementById("email").value.trim();
  resetPanel.classList.remove("hidden");
  document.getElementById("resetPassword").focus();
});

closeResetBtn.addEventListener("click", () => {
  resetPanel.classList.add("hidden");
  document.getElementById("resetForm").reset();
});

document.getElementById("resetForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const btn = document.getElementById("resetSubmitBtn");
  const email = document.getElementById("resetEmail").value.trim();
  const newPassword = document.getElementById("resetPassword").value;
  const confirmPassword = document.getElementById("resetPasswordConfirm").value;

  if (!email || !newPassword || !confirmPassword) {
    toast("Please complete all fields", "warning");
    return;
  }
  if (newPassword !== confirmPassword) {
    toast("Passwords do not match", "error");
    return;
  }
  if (newPassword.length < 6) {
    toast("Password must be at least 6 characters", "warning");
    return;
  }

  btn.disabled = true;
  btn.textContent = "Updating...";
  try {
    const data = await apiFetch("/api/auth/password-reset", {
      method: "POST",
      body: { email, new_password: newPassword, confirm_password: confirmPassword },
      auth: false,
    });
    toast(data.message || "Password reset successful", "success", 2500);
    resetPanel.classList.add("hidden");
    document.getElementById("resetForm").reset();
    document.getElementById("password").value = "";
  } catch (err) {
    toast(err.message, "error");
  } finally {
    btn.disabled = false;
    btn.textContent = "Update password";
  }
});
