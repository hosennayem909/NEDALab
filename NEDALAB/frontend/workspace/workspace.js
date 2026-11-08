requireAuth();
renderSidebar("workspace");
const user = getUser();

async function loadWorkspaces() {
  const list = document.getElementById("wsList");
  list.innerHTML = skeletonRows(2);
  try {
    const data = await apiFetch("/api/workspace/list");
    if (!data.length) {
      list.innerHTML = '<p class="text-sm text-stone-500">No workspaces yet.</p>';
      return;
    }
    list.innerHTML = data.map(ws => `
      <button data-slug="${ws.slug}"
        class="ws-item fade-in w-full text-left px-3 py-2 rounded-md border transition"
        style="border-color:#e7e5e4;background:white">
        <p class="font-medium text-stone-900">${ws.name}</p>
        <p class="text-xs text-stone-500">/${ws.slug}</p>
      </button>
    `).join("");
    list.querySelectorAll(".ws-item").forEach(el => {
      el.addEventListener("click", () => openWorkspace(el.dataset.slug));
    });
  } catch (err) {
    list.innerHTML = '<p class="text-sm text-red-600">' + err.message + '</p>';
  }
}

async function openWorkspace(slug) {
  const box = document.getElementById("wsDetail");
  box.innerHTML = '<div style="display:flex;align-items:center;gap:10px;color:#78716c;font-size:14px"><span class="spinner"></span> Loading...</div>';
  try {
    const data = await apiFetch("/api/workspace/" + slug);
    const ws = data.workspace, members = data.members;
    const myRole = data.my_role || "viewer";
    const canManage = myRole === "admin" || (user && user.role === "admin");

    box.innerHTML = `
      <div class="fade-in">
        <div class="flex justify-between items-start mb-6 pb-6 border-b" style="border-color:#e7e5e4">
          <div>
            <h2 class="text-xl font-bold text-stone-900">${ws.name}</h2>
            <p class="text-xs text-stone-500 mt-1">/${ws.slug}</p>
          </div>
          <span class="badge badge-emerald">Your role: ${myRole}</span>
        </div>

        <h3 class="text-xs font-semibold text-stone-500 uppercase tracking-wider mb-3">Members</h3>
        <div class="space-y-2 mb-6">
          ${members.map(m => `
            <div class="flex justify-between items-center border rounded-md px-3 py-2" style="border-color:#e7e5e4">
              <div>
                <p class="text-sm font-medium text-stone-800">${m.user_name}</p>
                <p class="text-xs text-stone-500">${m.user_email}</p>
              </div>
              <div class="flex items-center gap-3">
                <span class="badge badge-stone">${m.role}</span>
                ${canManage ? `<button data-mid="${m.id}" class="remove-member text-xs font-medium text-red-700 hover:text-red-800">Remove</button>` : ""}
              </div>
            </div>
          `).join("")}
        </div>

        ${canManage ? `
          <h3 class="text-xs font-semibold text-stone-500 uppercase tracking-wider mb-3">Add member</h3>
          <form id="addForm" class="flex flex-col sm:flex-row gap-3">
            <input id="addEmail" type="email" required placeholder="user@example.com" class="input flex-1" />
            <select id="addRole" class="input" style="width:auto">
              <option value="viewer">Viewer</option>
              <option value="researcher">Researcher</option>
              <option value="admin">Admin</option>
            </select>
            <button class="btn-primary">Add</button>
          </form>
        ` : ""}
      </div>
    `;

    if (canManage) {
      box.querySelector("#addForm").addEventListener("submit", async (e) => {
        e.preventDefault();
        try {
          await apiFetch("/api/workspace/" + slug + "/members", {
            method: "POST",
            body: {
              email: box.querySelector("#addEmail").value.trim(),
              role: box.querySelector("#addRole").value,
            },
          });
          toast("Member added", "success");
          openWorkspace(slug);
        } catch (err) {
          toast(err.message, "error");
        }
      });

      box.querySelectorAll(".remove-member").forEach(btn => {
        btn.addEventListener("click", async () => {
          if (!confirm("Remove this member?")) return;
          try {
            await apiFetch("/api/workspace/" + slug + "/members/" + btn.dataset.mid, { method: "DELETE" });
            toast("Member removed", "success");
            openWorkspace(slug);
          } catch (err) { toast(err.message, "error"); }
        });
      });
    }
  } catch (err) {
    box.innerHTML = '<p class="text-sm text-red-600">' + err.message + '</p>';
  }
}

document.getElementById("createForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  try {
    const ws = await apiFetch("/api/workspace/create", {
      method: "POST",
      body: { name: document.getElementById("wsName").value.trim() },
    });
    document.getElementById("wsName").value = "";
    toast("Workspace created", "success");
    await loadWorkspaces();
    openWorkspace(ws.slug);
  } catch (err) {
    toast(err.message, "error");
  }
});

loadWorkspaces();
