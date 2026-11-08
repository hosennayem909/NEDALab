requireAuth();
renderSidebar("profile");

async function loadProfile() {
  try {
    const p = await apiFetch("/api/auth/profile");
    document.getElementById("profileName").textContent = p.name;
    document.getElementById("profileEmail").textContent = p.email;
    document.getElementById("profileRole").textContent = p.role;
    document.getElementById("avatar").textContent = (p.name || "?")[0].toUpperCase();
    document.getElementById("editName").value = p.name;
    document.getElementById("editEmail").value = p.email;
    document.getElementById("statDs").textContent = p.stats.datasets;
    document.getElementById("statModels").textContent = p.stats.models;
    document.getElementById("statWs").textContent = p.stats.workspaces;
    document.getElementById("statAge").textContent = p.stats.account_age_days;
  } catch (err) {
    toast(err.message, "error");
  }
}

document.getElementById("profileForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const btn = e.target.querySelector("button");
  btn.disabled = true;
  try {
    const updated = await apiFetch("/api/auth/profile", {
      method: "PUT",
      body: { name: document.getElementById("editName").value.trim() },
    });
    // Update local storage session name
    const u = getUser();
    if (u) { u.name = updated.name; saveSession(localStorage.getItem("neda_token"), u); }
    toast("Profile updated", "success");
    loadProfile();
    // update sidebar
    document.getElementById("sideUserName").textContent = updated.name;
  } catch (err) {
    toast(err.message, "error");
  } finally {
    btn.disabled = false;
  }
});

document.getElementById("passwordForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const curPass = document.getElementById("curPass").value;
  const newPass = document.getElementById("newPass").value;
  const confirmPass = document.getElementById("confirmPass").value;

  if (newPass !== confirmPass) {
    toast("New passwords do not match", "error");
    return;
  }

  const btn = e.target.querySelector("button");
  btn.disabled = true;
  try {
    await apiFetch("/api/auth/change-password", {
      method: "POST",
      body: { current_password: curPass, new_password: newPass },
    });
    toast("Password updated successfully", "success");
    e.target.reset();
  } catch (err) {
    toast(err.message, "error");
  } finally {
    btn.disabled = false;
  }
});

loadProfile();
