document.getElementById("registerForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const btn = document.getElementById("submitBtn");
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner" style="border-color:rgba(255,255,255,0.3);border-top-color:white"></span>';

  const payload = {
    name: document.getElementById("name").value.trim(),
    email: document.getElementById("email").value.trim(),
    password: document.getElementById("password").value,
    role: document.getElementById("role").value,
  };
  try {
    const data = await apiFetch("/api/auth/register", { method: "POST", body: payload, auth: false });
    saveSession(data.access_token, data.user);
    toast("Account created. Welcome!", "success", 1500);
    setTimeout(() => window.location.href = "../dashboard/dashboard.html", 500);
  } catch (err) {
    toast(err.message, "error");
    btn.disabled = false;
    btn.textContent = "Create account";
  }
});
