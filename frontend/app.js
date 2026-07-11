// ===========================================================================
// TRAMEX SYSTEM - SINGLE PAGE APPLICATION LOGIC
// ===========================================================================

const API_BASE_URL = "http://localhost:8000";

// Configuración de campos dinámicos para cada recurso en la base de datos
const RESOURCE_CONFIGS = {
    master_tramex: {
        title: "Master Tramex",
        endpoint: "/api/master-tramex/",
        headers: ["ID", "Nombre", "ID Solicitud", "Teléfono", "Pasaporte", "Trámite", "Cita", "Correo", "Cargado En", "Acciones"],
        fields: [
            { name: "nombre", label: "Nombre Completo", type: "text", required: true, grid: true },
            { name: "id_solicitud", label: "ID Solicitud", type: "text", required: false },
            { name: "telefono", label: "Teléfono", type: "text", required: false },
            { name: "numero_pasaporte", label: "Número de Pasaporte", type: "text", required: false },
            { name: "correo_electronico", label: "Correo Electrónico", type: "email", required: false },
            { name: "tramite", label: "Tipo de Trámite", type: "text", required: false },
            { name: "cita", label: "Estado/Fecha Cita", type: "text", required: false },
            { name: "contrasena", label: "Contraseña de la Cuenta", type: "password", required: false }
        ]
    },
    global_entry: {
        title: "Global Entry",
        endpoint: "/api/global-entry/",
        headers: ["ID", "Nombre", "Apellido", "Correo", "Pasaporte", "Cargado En", "Acciones"],
        fields: [
            { name: "nombre", label: "Nombre", type: "text", required: true },
            { name: "apellido", label: "Apellido", type: "text", required: false },
            { name: "correo_electronico", label: "Correo Electrónico", type: "email", required: false, grid: true },
            { name: "numero_pasaporte", label: "Número de Pasaporte", type: "text", required: false },
            { name: "contrasena", label: "Contraseña / No. Cuenta", type: "password", required: false }
        ]
    },
    pasaportes: {
        title: "Pasaportes",
        endpoint: "/api/pasaportes/",
        headers: ["ID", "Nombre", "Apellido", "Teléfono", "Lugar Cita", "Fecha Cita", "Texto Original", "Cargado En", "Acciones"],
        fields: [
            { name: "nombre", label: "Nombre", type: "text", required: true },
            { name: "apellido", label: "Apellido", type: "text", required: false },
            { name: "telefono", label: "Teléfono", type: "text", required: false },
            { name: "lugar_cita", label: "Lugar de la Cita", type: "text", required: false },
            { name: "fecha_cita", label: "Fecha Cita (YYYY-MM-DD)", type: "date", required: false },
            { name: "fecha_cita_original", label: "Fecha Cita (Texto Original)", type: "text", required: false }
        ]
    },
    canada: {
        title: "Canadá",
        endpoint: "/api/canada/",
        headers: ["ID", "Nombre", "Cuenta IRCC", "Teléfono", "Pasaporte", "Cargado En", "Acciones"],
        fields: [
            { name: "nombre", label: "Nombre Completo", type: "text", required: true, grid: true },
            { name: "cuenta_ircc", label: "Cuenta IRCC", type: "text", required: false },
            { name: "telefono", label: "Teléfono", type: "text", required: false },
            { name: "numero_pasaporte", label: "Número de Pasaporte", type: "text", required: false },
            { name: "contrasena", label: "Contraseña Cita", type: "password", required: false }
        ]
    }
};

// Estado global de la aplicación
const state = {
    token: localStorage.getItem("tramex_token") || null,
    activeTab: "dashboard", // "dashboard", "master_tramex", "global_entry", "pasaportes", "canada"
    searchQuery: "",
    skip: 0,
    limit: 10,
    totalRecords: 0,
    activeRecord: null, // Para editar/borrar/ver contraseña
    isEditing: false
};

// ===========================================================================
// INICIALIZACIÓN Y CONTROLADORES DE RUTA/PANTALLAS
// ===========================================================================

document.addEventListener("DOMContentLoaded", () => {
    initApp();
    setupEventListeners();
});

function initApp() {
    if (state.token) {
        verifyTokenAndLoadDashboard();
    } else {
        showScreen("login-screen");
    }
}

async function verifyTokenAndLoadDashboard() {
    try {
        const response = await fetch(`${API_BASE_URL}/health`, {
            headers: { "Authorization": `Bearer ${state.token}` }
        });
        if (response.ok) {
            showScreen("main-screen");
            showTab("dashboard");
        } else {
            handleLogout();
        }
    } catch (err) {
        showToast("Error de conexión con la API. Trabajando en modo local/desconectado.", "error");
        showScreen("main-screen");
        showTab("dashboard");
    }
}

function showScreen(screenId) {
    document.querySelectorAll(".screen").forEach(s => s.classList.remove("active"));
    document.getElementById(screenId).classList.add("active");
}

function showTab(tabId) {
    state.activeTab = tabId;
    state.skip = 0;
    state.searchQuery = "";
    
    // Resetear buscador
    const searchInput = document.getElementById("input-search");
    if (searchInput) searchInput.value = "";

    // Actualizar menú activo en Sidebar
    document.querySelectorAll(".menu-item").forEach(item => {
        item.classList.remove("active");
        if (item.getAttribute("data-target") === tabId) {
            item.classList.add("active");
        }
    });

    // Cambiar título de navbar superior
    const titleEl = document.getElementById("current-page-title");
    if (tabId === "dashboard") {
        titleEl.textContent = "Resumen del Sistema";
    } else {
        titleEl.textContent = `Administración de ${RESOURCE_CONFIGS[tabId].title}`;
    }

    // Alternar vistas
    document.querySelectorAll(".view").forEach(v => v.classList.remove("active"));
    if (tabId === "dashboard") {
        document.getElementById("view-dashboard").classList.add("active");
        loadDashboardStats();
    } else {
        document.getElementById("view-crud").classList.add("active");
        loadCrudView();
    }
}

// ===========================================================================
// PETICIONES Y RENDERIZADO DEL DASHBOARD GENERAL
// ===========================================================================

async function loadDashboardStats() {
    const resources = ["master_tramex", "global_entry", "pasaportes", "canada"];
    const counts = { master_tramex: "count-master", global_entry: "count-global", pasaportes: "count-pasaportes", canada: "count-canada" };

    // Actualizar estado de conexión a la BD
    try {
        const healthRes = await fetch(`${API_BASE_URL}/health`);
        const statusBadge = document.getElementById("db-status");
        if (healthRes.ok) {
            statusBadge.className = "api-status-badge success";
            statusBadge.querySelector("span").textContent = "BD Conectada";
        } else {
            statusBadge.className = "api-status-badge error";
            statusBadge.querySelector("span").textContent = "BD Desconectada";
        }
    } catch {
        const statusBadge = document.getElementById("db-status");
        statusBadge.className = "api-status-badge error";
        statusBadge.querySelector("span").textContent = "BD Desconectada";
    }

    // Solicitar conteos en paralelo
    resources.forEach(async (key) => {
        const config = RESOURCE_CONFIGS[key];
        const numEl = document.getElementById(counts[key]);
        numEl.textContent = "...";
        try {
            const res = await fetch(`${API_BASE_URL}${config.endpoint}?limit=1`, {
                headers: { "Authorization": `Bearer ${state.token}` }
            });
            if (res.ok) {
                const data = await res.json();
                numEl.textContent = data.total.toLocaleString();
            } else {
                numEl.textContent = "Error";
            }
        } catch {
            numEl.textContent = "N/A";
        }
    });
}

// ===========================================================================
// PETICIONES Y RENDERIZADO DE LA VISTA CRUD
// ===========================================================================

async function loadCrudView() {
    const config = RESOURCE_CONFIGS[state.activeTab];
    if (!config) return;

    const table = document.getElementById("data-table");
    const thead = table.querySelector("thead");
    const tbody = table.querySelector("tbody");

    // Renderizar cabeceras
    thead.innerHTML = `<tr>${config.headers.map(h => `<th>${h}</th>`).join("")}</tr>`;
    tbody.innerHTML = `<tr><td colspan="${config.headers.length}" class="text-center"><i class="fa-solid fa-spinner fa-spin"></i> Cargando información...</td></tr>`;

    try {
        let url = `${API_BASE_URL}${config.endpoint}?skip=${state.skip}&limit=${state.limit}`;
        if (state.searchQuery) {
            url += `&buscar=${encodeURIComponent(state.searchQuery)}`;
        }

        const res = await fetch(url, {
            headers: { "Authorization": `Bearer ${state.token}` }
        });

        if (res.status === 401) {
            handleLogout();
            return;
        }

        if (res.ok) {
            const data = await res.json();
            state.totalRecords = data.total;
            renderTableRows(data.items);
            updatePaginationInfo();
        } else {
            tbody.innerHTML = `<tr><td colspan="${config.headers.length}" class="text-danger"><i class="fa-solid fa-circle-xmark"></i> Error al cargar datos del servidor.</td></tr>`;
        }
    } catch (err) {
        tbody.innerHTML = `<tr><td colspan="${config.headers.length}" class="text-danger"><i class="fa-solid fa-triangle-exclamation"></i> Error de conexión con el backend.</td></tr>`;
    }
}

function renderTableRows(items) {
    const tbody = document.querySelector("#data-table tbody");
    const config = RESOURCE_CONFIGS[state.activeTab];
    
    if (items.length === 0) {
        tbody.innerHTML = `<tr><td colspan="${config.headers.length}" class="text-muted text-center">No se encontraron trámites registrados.</td></tr>`;
        return;
    }

    tbody.innerHTML = items.map(item => {
        let colsHtml = "";
        
        // Renderizado condicional según la tabla activa
        if (state.activeTab === "master_tramex") {
            colsHtml += `<td>${item.id}</td>`;
            colsHtml += `<td><strong>${item.nombre}</strong></td>`;
            colsHtml += `<td><span class="badge-mono">${item.id_solicitud || "-"}</span></td>`;
            colsHtml += `<td>${item.telefono || "-"}</td>`;
            colsHtml += `<td>${item.numero_pasaporte || "-"}</td>`;
            colsHtml += `<td>${item.tramite || "-"}</td>`;
            colsHtml += `<td>${item.cita || "-"}</td>`;
            colsHtml += `<td>${item.correo_electronico || "-"}</td>`;
            colsHtml += `<td>${formatDate(item.cargado_en)}</td>`;
        } else if (state.activeTab === "global_entry") {
            colsHtml += `<td>${item.id}</td>`;
            colsHtml += `<td><strong>${item.nombre}</strong></td>`;
            colsHtml += `<td>${item.apellido || "-"}</td>`;
            colsHtml += `<td>${item.correo_electronico || "-"}</td>`;
            colsHtml += `<td>${item.numero_pasaporte || "-"}</td>`;
            colsHtml += `<td>${formatDate(item.cargado_en)}</td>`;
        } else if (state.activeTab === "pasaportes") {
            colsHtml += `<td>${item.id}</td>`;
            colsHtml += `<td><strong>${item.nombre}</strong></td>`;
            colsHtml += `<td>${item.apellido || "-"}</td>`;
            colsHtml += `<td>${item.telefono || "-"}</td>`;
            colsHtml += `<td>${item.lugar_cita || "-"}</td>`;
            colsHtml += `<td>${item.fecha_cita || "-"}</td>`;
            colsHtml += `<td><span class="text-muted">${item.fecha_cita_original || "-"}</span></td>`;
            colsHtml += `<td>${formatDate(item.cargado_en)}</td>`;
        } else if (state.activeTab === "canada") {
            colsHtml += `<td>${item.id}</td>`;
            colsHtml += `<td><strong>${item.nombre}</strong></td>`;
            colsHtml += `<td>${item.cuenta_ircc || "-"}</td>`;
            colsHtml += `<td>${item.telefono || "-"}</td>`;
            colsHtml += `<td>${item.numero_pasaporte || "-"}</td>`;
            colsHtml += `<td>${formatDate(item.cargado_en)}</td>`;
        }

        // Agregar botones de acción comunes
        const hasPassword = ["master_tramex", "global_entry", "canada"].includes(state.activeTab);
        const actionButtons = `
            <div class="table-actions">
                ${hasPassword ? `<button class="btn-icon text-secondary" onclick="viewPassword(${item.id})" title="Ver Contraseña"><i class="fa-solid fa-key"></i></button>` : ""}
                <button class="btn-icon" onclick="editRecord(${JSON.stringify(item).replace(/"/g, '&quot;')})" title="Editar"><i class="fa-solid fa-pen-to-square"></i></button>
                <button class="btn-icon danger" onclick="confirmDeleteRecord(${item.id})" title="Eliminar"><i class="fa-solid fa-trash-can"></i></button>
            </div>
        `;
        colsHtml += `<td>${actionButtons}</td>`;

        return `<tr>${colsHtml}</tr>`;
    }).join("");
}

function updatePaginationInfo() {
    const start = state.skip + 1;
    const end = Math.min(state.skip + state.limit, state.totalRecords);
    const infoText = state.totalRecords > 0 
        ? `Mostrando ${start} a ${end} de ${state.totalRecords} registros`
        : "No hay registros";
    
    document.getElementById("pagination-info").textContent = infoText;

    // Habilitar/deshabilitar botones
    document.getElementById("btn-prev").disabled = state.skip === 0;
    document.getElementById("btn-next").disabled = end >= state.totalRecords;
}

// ===========================================================================
// OPERACIONES CRUD (CREAR, EDITAR, ELIMINAR, VER PASSWORD)
// ===========================================================================

// 1. Mostrar/Generar Formulario en Modal
function openRecordModal(isEdit = false, data = null) {
    state.isEditing = isEdit;
    state.activeRecord = data;

    const modal = document.getElementById("modal-record");
    const title = document.getElementById("modal-title");
    const container = document.getElementById("modal-fields-container");
    const config = RESOURCE_CONFIGS[state.activeTab];

    title.textContent = isEdit ? `Editar Registro #${data.id}` : `Agregar a ${config.title}`;
    container.innerHTML = "";

    // Inyectar campos de forma dinámica basándose en la configuración
    config.fields.forEach(field => {
        const fieldWrapper = document.createElement("div");
        fieldWrapper.className = `form-group ${field.grid ? "grid-col-2" : ""}`;
        
        const label = document.createElement("label");
        label.setAttribute("for", `f-${field.name}`);
        label.textContent = field.label;

        let input;
        if (field.type === "password") {
            // El input de contraseña requiere el ojo para mostrar/ocultar texto
            const wrapper = document.createElement("div");
            wrapper.className = "password-input-wrapper";
            
            input = document.createElement("input");
            input.type = "password";
            input.id = `f-${field.name}`;
            input.name = field.name;
            input.placeholder = isEdit ? "Dejar vacío para no cambiar" : "Contraseña de la cuenta";
            
            const btnToggle = document.createElement("button");
            btnToggle.type = "button";
            btnToggle.className = "btn-toggle-pwd";
            btnToggle.innerHTML = '<i class="fa-solid fa-eye"></i>';
            btnToggle.onclick = () => {
                input.type = input.type === "password" ? "text" : "password";
                btnToggle.innerHTML = input.type === "password" ? '<i class="fa-solid fa-eye"></i>' : '<i class="fa-solid fa-eye-slash"></i>';
            };
            
            wrapper.appendChild(input);
            wrapper.appendChild(btnToggle);
            
            fieldWrapper.appendChild(label);
            fieldWrapper.appendChild(wrapper);
        } else {
            input = document.createElement("input");
            input.type = field.type;
            input.id = `f-${field.name}`;
            input.name = field.name;
            input.required = field.required;
            
            // Llenar valores en caso de edición
            if (isEdit && data[field.name] !== undefined) {
                input.value = data[field.name] || "";
            }
            
            fieldWrapper.appendChild(label);
            fieldWrapper.appendChild(input);
        }

        container.appendChild(fieldWrapper);
    });

    modal.classList.add("active");
}

// 2. Guardar Registro (POST o PATCH)
async function handleSaveRecord(e) {
    e.preventDefault();
    const config = RESOURCE_CONFIGS[state.activeTab];
    const form = document.getElementById("record-form");
    const formData = new FormData(form);
    const payload = {};

    // Construir payload
    config.fields.forEach(field => {
        const val = formData.get(field.name);
        if (state.isEditing && field.type === "password" && !val) {
            // No incluir contraseña vacía en edición
            return;
        }
        payload[field.name] = val || null;
    });

    try {
        let url = `${API_BASE_URL}${config.endpoint}`;
        let method = "POST";
        
        if (state.isEditing) {
            url += state.activeRecord.id;
            method = "PATCH";
        }

        const res = await fetch(url, {
            method: method,
            headers: {
                "Content-Type": "application/json",
                "Authorization": `Bearer ${state.token}`
            },
            body: JSON.stringify(payload)
        });

        if (res.ok) {
            closeModals();
            showToast(state.isEditing ? "Registro actualizado." : "Registro creado.", "success");
            loadCrudView();
        } else {
            const errData = await res.json();
            const errMsg = errData.detail && typeof errData.detail === "object"
                ? errData.detail[0]?.msg
                : errData.detail;
            showToast(`Error: ${errMsg || "No se pudo guardar."}`, "error");
        }
    } catch {
        showToast("Error de conexión al guardar el registro.", "error");
    }
}

// 3. Ver Contraseña Descifrada (Llamada al endpoint seguro)
window.viewPassword = async function(id) {
    const config = RESOURCE_CONFIGS[state.activeTab];
    try {
        const res = await fetch(`${API_BASE_URL}${config.endpoint}${id}/password`, {
            headers: { "Authorization": `Bearer ${state.token}` }
        });
        if (res.ok) {
            const data = await res.json();
            const password = data.contrasena || "[Sin contraseña asignada]";
            
            document.getElementById("decrypted-pwd-text").textContent = password;
            document.getElementById("modal-password").classList.add("active");
            
            // Asignar evento al botón de copiar
            document.getElementById("btn-copy-pwd").onclick = () => {
                navigator.clipboard.writeText(password);
                showToast("Contraseña copiada al portapapeles.", "info");
            };
        } else {
            showToast("No se pudo descifrar la contraseña.", "error");
        }
    } catch {
        showToast("Error de conexión al descifrar.", "error");
    }
};

// 4. Iniciar Edición desde la tabla
window.editRecord = function(item) {
    openRecordModal(true, item);
};

// 5. Confirmar eliminación
window.confirmDeleteRecord = function(id) {
    state.activeRecord = { id: id };
    document.getElementById("modal-delete").classList.add("active");
};

async function executeDelete() {
    const config = RESOURCE_CONFIGS[state.activeTab];
    try {
        const res = await fetch(`${API_BASE_URL}${config.endpoint}${state.activeRecord.id}`, {
            method: "DELETE",
            headers: { "Authorization": `Bearer ${state.token}` }
        });
        if (res.ok) {
            closeModals();
            showToast("Registro eliminado correctamente.", "success");
            loadCrudView();
        } else {
            showToast("No se pudo eliminar el registro.", "error");
        }
    } catch {
        showToast("Error de conexión al eliminar.", "error");
    }
}

// ===========================================================================
// LOGIN, LOGOUT Y EVENTOS DE INTERFAZ
// ===========================================================================

async function handleLogin(e) {
    e.preventDefault();
    const usernameInput = document.getElementById("username").value;
    const passwordInput = document.getElementById("password").value;
    const errorEl = document.getElementById("login-error");
    const errMsgEl = document.getElementById("error-message");

    errorEl.classList.add("hidden");

    const bodyParams = new URLSearchParams();
    bodyParams.append("username", usernameInput);
    bodyParams.append("password", passwordInput);

    try {
        const res = await fetch(`${API_BASE_URL}/api/auth/token`, {
            method: "POST",
            headers: { "Content-Type": "application/x-www-form-urlencoded" },
            body: bodyParams
        });

        if (res.ok) {
            const data = await res.json();
            state.token = data.access_token;
            localStorage.setItem("tramex_token", data.access_token);
            
            showScreen("main-screen");
            showTab("dashboard");
            showToast("Sesión iniciada correctamente.", "success");
        } else {
            const data = await res.json();
            errMsgEl.textContent = data.detail || "Credenciales inválidas.";
            errorEl.classList.remove("hidden");
        }
    } catch {
        errMsgEl.textContent = "Error de conexión con el servidor.";
        errorEl.classList.remove("hidden");
    }
}

function handleLogout() {
    state.token = null;
    localStorage.removeItem("tramex_token");
    showScreen("login-screen");
    // Limpiar campos de login
    document.getElementById("login-form").reset();
    document.getElementById("login-error").classList.add("hidden");
}

function setupEventListeners() {
    // Formularios
    document.getElementById("login-form").addEventListener("submit", handleLogin);
    document.getElementById("record-form").addEventListener("submit", handleSaveRecord);

    // Botón Salir
    document.getElementById("btn-logout").addEventListener("click", handleLogout);

    // Navegación Sidebar
    document.querySelectorAll(".menu-item").forEach(item => {
        item.addEventListener("click", () => {
            const target = item.getAttribute("data-target");
            showTab(target);
        });
    });

    // Modales (Cerrar)
    document.querySelectorAll(".btn-close-modal").forEach(btn => {
        btn.addEventListener("click", closeModals);
    });

    // Abrir Modal de creación
    document.getElementById("btn-add-record").addEventListener("click", () => {
        openRecordModal(false);
    });

    // Paginación
    document.getElementById("btn-prev").addEventListener("click", () => {
        if (state.skip >= state.limit) {
            state.skip -= state.limit;
            loadCrudView();
        }
    });
    document.getElementById("btn-next").addEventListener("click", () => {
        if (state.skip + state.limit < state.totalRecords) {
            state.skip += state.limit;
            loadCrudView();
        }
    });

    // Búsqueda en tiempo real
    const searchInput = document.getElementById("input-search");
    let searchTimeout;
    searchInput.addEventListener("input", (e) => {
        clearTimeout(searchTimeout);
        searchTimeout = setTimeout(() => {
            state.searchQuery = e.target.value;
            state.skip = 0; // Volver a la primera página en búsquedas
            loadCrudView();
        }, 350); // Delay de 350ms para no saturar al backend
    });

    // Toggle ocultar password en login
    document.getElementById("toggle-login-password").addEventListener("click", function() {
        const pwdInput = document.getElementById("password");
        const type = pwdInput.getAttribute("type") === "password" ? "text" : "password";
        pwdInput.setAttribute("type", type);
        this.innerHTML = type === "password" ? '<i class="fa-solid fa-eye"></i>' : '<i class="fa-solid fa-eye-slash"></i>';
    });

    // Confirmación eliminación
    document.getElementById("btn-confirm-delete").addEventListener("click", executeDelete);
}

function closeModals() {
    document.querySelectorAll(".modal").forEach(m => m.classList.remove("active"));
    state.activeRecord = null;
    state.isEditing = false;
}

// ===========================================================================
// UTILERÍAS / INTERFAZ
// ===========================================================================

function formatDate(isoString) {
    if (!isoString) return "-";
    try {
        const d = new Date(isoString);
        return d.toLocaleDateString("es-MX", {
            year: "numeric",
            month: "2-digit",
            day: "2-digit",
            hour: "2-digit",
            minute: "2-digit"
        });
    } catch {
        return isoString;
    }
}

function showToast(message, type = "info") {
    const container = document.getElementById("toast-container");
    const toast = document.createElement("div");
    toast.className = `toast ${type}`;
    
    let icon = '<i class="fa-solid fa-info-circle"></i>';
    if (type === "success") icon = '<i class="fa-solid fa-circle-check"></i>';
    if (type === "error") icon = '<i class="fa-solid fa-circle-exclamation"></i>';

    toast.innerHTML = `${icon} <span>${message}</span>`;
    container.appendChild(toast);

    // Animación de salida y remoción
    setTimeout(() => {
        toast.style.animation = "slideIn 0.3s reverse forwards";
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}
