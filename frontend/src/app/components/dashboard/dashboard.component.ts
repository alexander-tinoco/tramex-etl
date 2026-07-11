import { Component, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { ApiService } from '../../services/api.service';
import { AuthService } from '../../services/auth.service';

interface Field {
  name: string;
  label: string;
  type: string;
  required?: boolean;
  grid?: boolean;
}

interface ResourceConfig {
  title: string;
  endpoint: string;
  headers: string[];
  fields: Field[];
}

const RESOURCE_CONFIGS: Record<string, ResourceConfig> = {
  master_tramex: {
    title: "Master Tramex",
    endpoint: "/master-tramex/",
    headers: ["ID", "Nombre", "ID Solicitud", "Teléfono", "Pasaporte", "Trámite", "Cita", "Correo", "Cargado En", "Acciones"],
    fields: [
      { name: "nombre", label: "Nombre Completo", type: "text", required: true, grid: true },
      { name: "id_solicitud", label: "ID Solicitud", type: "text" },
      { name: "telefono", label: "Teléfono", type: "text" },
      { name: "numero_pasaporte", label: "Número de Pasaporte", type: "text" },
      { name: "correo_electronico", label: "Correo Electrónico", type: "email" },
      { name: "tramite", label: "Tipo de Trámite", type: "text" },
      { name: "cita", label: "Estado/Fecha Cita", type: "text" },
      { name: "contrasena", label: "Contraseña de la Cuenta", type: "password" }
    ]
  },
  global_entry: {
    title: "Global Entry",
    endpoint: "/global-entry/",
    headers: ["ID", "Nombre", "Apellido", "Correo", "Pasaporte", "Cargado En", "Acciones"],
    fields: [
      { name: "nombre", label: "Nombre", type: "text", required: true },
      { name: "apellido", label: "Apellido", type: "text" },
      { name: "correo_electronico", label: "Correo Electrónico", type: "email", grid: true },
      { name: "numero_pasaporte", label: "Número de Pasaporte", type: "text" },
      { name: "contrasena", label: "Contraseña / No. Cuenta", type: "password" }
    ]
  },
  pasaportes: {
    title: "Pasaportes",
    endpoint: "/pasaportes/",
    headers: ["ID", "Nombre", "Apellido", "Teléfono", "Lugar Cita", "Fecha Cita", "Texto Original", "Cargado En", "Acciones"],
    fields: [
      { name: "nombre", label: "Nombre", type: "text", required: true },
      { name: "apellido", label: "Apellido", type: "text" },
      { name: "telefono", label: "Teléfono", type: "text" },
      { name: "lugar_cita", label: "Lugar de la Cita", type: "text" },
      { name: "fecha_cita", label: "Fecha Cita (YYYY-MM-DD)", type: "date" },
      { name: "fecha_cita_original", label: "Fecha Cita (Texto Original)", type: "text" }
    ]
  },
  canada: {
    title: "Canadá",
    endpoint: "/canada/",
    headers: ["ID", "Nombre", "Cuenta IRCC", "Teléfono", "Pasaporte", "Cargado En", "Acciones"],
    fields: [
      { name: "nombre", label: "Nombre Completo", type: "text", required: true, grid: true },
      { name: "cuenta_ircc", label: "Cuenta IRCC", type: "text" },
      { name: "telefono", label: "Teléfono", type: "text" },
      { name: "numero_pasaporte", label: "Número de Pasaporte", type: "text" },
      { name: "contrasena", label: "Contraseña Cita", type: "password" }
    ]
  }
};

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './dashboard.component.html',
  styles: []
})
export class DashboardComponent implements OnInit {
  private api = inject(ApiService);
  private auth = inject(AuthService);
  private router = inject(Router);

  activeTab = 'dashboard';
  pageTitle = 'Resumen del Sistema';
  dbConnected = false;
  
  // Dashboard counts
  counts: Record<string, string> = {
    master_tramex: '-',
    global_entry: '-',
    pasaportes: '-',
    canada: '-'
  };

  // CRUD State
  items: any[] = [];
  loadingData = false;
  searchQuery = '';
  searchTimeout: any;
  
  skip = 0;
  limit = 10;
  totalRecords = 0;

  // Modal control
  showRecordModal = false;
  showPasswordModal = false;
  showDeleteModal = false;
  
  isEditing = false;
  activeId: number | null = null;
  decryptedPassword = '';
  showModalPassword = false;
  
  formValues: Record<string, any> = {};
  
  // Toasts
  toasts: {message: string, type: string}[] = [];

  ngOnInit() {
    this.checkHealth();
    this.loadDashboardCounts();
  }

  get activeConfig(): ResourceConfig {
    return RESOURCE_CONFIGS[this.activeTab];
  }

  setTab(tab: string) {
    this.activeTab = tab;
    this.skip = 0;
    this.searchQuery = '';
    this.items = [];
    
    if (tab === 'dashboard') {
      this.pageTitle = 'Resumen del Sistema';
      this.loadDashboardCounts();
    } else {
      this.pageTitle = `Administración de ${RESOURCE_CONFIGS[tab].title}`;
      this.loadCrudData();
    }
  }

  checkHealth() {
    this.api.checkHealth().subscribe({
      next: (data) => {
        this.dbConnected = data.database === 'connected';
      },
      error: (err) => {
        this.dbConnected = false;
        if (err.status === 401) {
          this.logout();
        }
      }
    });
  }

  loadDashboardCounts() {
    const resources = ['master_tramex', 'global_entry', 'pasaportes', 'canada'];
    resources.forEach(key => {
      const endpoint = RESOURCE_CONFIGS[key].endpoint;
      this.api.getList(endpoint, 0, 1).subscribe({
        next: (data) => {
          this.counts[key] = data.total.toLocaleString();
        },
        error: () => {
          this.counts[key] = 'N/A';
        }
      });
    });
  }

  loadCrudData() {
    this.loadingData = true;
    const endpoint = this.activeConfig.endpoint;
    this.api.getList(endpoint, this.skip, this.limit, this.searchQuery).subscribe({
      next: (data) => {
        this.totalRecords = data.total;
        this.items = data.items;
        this.loadingData = false;
      },
      error: (err) => {
        this.loadingData = false;
        this.showToast('Error al conectar con la base de datos.', 'error');
        if (err.status === 401) {
          this.logout();
        }
      }
    });
  }

  onSearch() {
    clearTimeout(this.searchTimeout);
    this.searchTimeout = setTimeout(() => {
      this.skip = 0;
      this.loadCrudData();
    }, 350);
  }

  prevPage() {
    if (this.skip >= this.limit) {
      this.skip -= this.limit;
      this.loadCrudData();
    }
  }

  nextPage() {
    if (this.skip + this.limit < this.totalRecords) {
      this.skip += this.limit;
      this.loadCrudData();
    }
  }

  getStartRange(): number {
    return this.totalRecords === 0 ? 0 : this.skip + 1;
  }

  getEndRange(): number {
    return Math.min(this.skip + this.limit, this.totalRecords);
  }

  hasPassword(): boolean {
    return ['master_tramex', 'global_entry', 'canada'].includes(this.activeTab);
  }

  // MODALS
  openAddModal() {
    this.isEditing = false;
    this.activeId = null;
    this.formValues = {};
    this.showModalPassword = false;
    
    // Inicializar campos vacíos
    this.activeConfig.fields.forEach(f => {
      this.formValues[f.name] = '';
    });
    
    this.showRecordModal = true;
  }

  openEditModal(item: any) {
    this.isEditing = true;
    this.activeId = item.id;
    this.formValues = { ...item };
    this.showModalPassword = false;
    
    // No queremos cargar contraseñas en el formulario de edición por defecto
    if (this.formValues['contrasena'] !== undefined) {
      this.formValues['contrasena'] = '';
    }
    
    this.showRecordModal = true;
  }

  confirmDelete(id: number) {
    this.activeId = id;
    this.showDeleteModal = true;
  }

  viewPassword(id: number) {
    this.activeId = id;
    this.api.getPassword(this.activeConfig.endpoint, id).subscribe({
      next: (data) => {
        this.decryptedPassword = data.contrasena || '[Sin contraseña asignada]';
        this.showPasswordModal = true;
      },
      error: () => {
        this.showToast('No se pudo descifrar la contraseña.', 'error');
      }
    });
  }

  copyPassword() {
    navigator.clipboard.writeText(this.decryptedPassword);
    this.showToast('Contraseña copiada al portapapeles.', 'info');
  }

  closeModals() {
    this.showRecordModal = false;
    this.showPasswordModal = false;
    this.showDeleteModal = false;
    this.activeId = null;
  }

  toggleModalPassword() {
    this.showModalPassword = !this.showModalPassword;
  }

  saveRecord(event: Event) {
    event.preventDefault();
    const endpoint = this.activeConfig.endpoint;
    
    // Limpiar campos nulos o vacíos en la edición
    const payload: Record<string, any> = {};
    this.activeConfig.fields.forEach(f => {
      const val = this.formValues[f.name];
      if (this.isEditing && f.type === 'password' && !val) {
        return; // Excluir campo de contraseña vacío en edición
      }
      payload[f.name] = val || null;
    });

    if (this.isEditing && this.activeId) {
      this.api.updateRecord(endpoint, this.activeId, payload).subscribe({
        next: () => {
          this.closeModals();
          this.showToast('Registro actualizado.', 'success');
          this.loadCrudData();
        },
        error: () => this.showToast('Error al actualizar el registro.', 'error')
      });
    } else {
      this.api.createRecord(endpoint, payload).subscribe({
        next: () => {
          this.closeModals();
          this.showToast('Registro creado.', 'success');
          this.loadCrudData();
        },
        error: () => this.showToast('Error al crear el registro.', 'error')
      });
    }
  }

  deleteRecord() {
    if (!this.activeId) return;
    this.api.deleteRecord(this.activeConfig.endpoint, this.activeId).subscribe({
      next: () => {
        this.closeModals();
        this.showToast('Registro eliminado.', 'success');
        this.loadCrudData();
      },
      error: () => this.showToast('Error al eliminar el registro.', 'error')
    });
  }

  // UTILS
  formatDate(isoString: string): string {
    if (!isoString) return '-';
    try {
      const d = new Date(isoString);
      return d.toLocaleDateString('es-MX', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit'
      });
    } catch {
      return isoString;
    }
  }

  showToast(message: string, type: string) {
    const toast = { message, type };
    this.toasts.push(toast);
    setTimeout(() => {
      this.toasts = this.toasts.filter(t => t !== toast);
    }, 4000);
  }

  getToastIcon(type: string): string {
    if (type === 'success') return 'fa-circle-check';
    if (type === 'error') return 'fa-circle-exclamation';
    return 'fa-info-circle';
  }

  logout() {
    this.auth.logout();
    this.router.navigate(['/login']);
  }
}
