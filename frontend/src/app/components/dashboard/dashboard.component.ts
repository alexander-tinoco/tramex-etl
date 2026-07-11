import { Component, OnInit } from '@angular/core';
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
    endpoint: "/api/master-tramex/",
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
    endpoint: "/api/global-entry/",
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
    endpoint: "/api/pasaportes/",
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
    endpoint: "/api/canada/",
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
  template: `
    <div id="main-screen" class="screen active">
      <!-- SIDEBAR -->
      <aside class="sidebar">
        <div class="sidebar-brand">
          <i class="fa-solid fa-passport icon-brand"></i>
          <h2>Tramex</h2>
        </div>
        <nav class="sidebar-menu">
          <ul>
            <li class="menu-item" [ngClass]="{'active': activeTab === 'dashboard'}" (click)="setTab('dashboard')">
              <i class="fa-solid fa-chart-line"></i> <span>Dashboard</span>
            </li>
            <li class="menu-item" [ngClass]="{'active': activeTab === 'master_tramex'}" (click)="setTab('master_tramex')">
              <i class="fa-solid fa-list-check"></i> <span>Master Tramex</span>
            </li>
            <li class="menu-item" [ngClass]="{'active': activeTab === 'global_entry'}" (click)="setTab('global_entry')">
              <i class="fa-solid fa-globe"></i> <span>Global Entry</span>
            </li>
            <li class="menu-item" [ngClass]="{'active': activeTab === 'pasaportes'}" (click)="setTab('pasaportes')">
              <i class="fa-solid fa-book-bookmark"></i> <span>Pasaportes</span>
            </li>
            <li class="menu-item" [ngClass]="{'active': activeTab === 'canada'}" (click)="setTab('canada')">
              <i class="fa-solid fa-map"></i> <span>Canadá</span>
            </li>
          </ul>
        </nav>
        <div class="sidebar-footer">
          <button id="btn-logout" class="btn-secondary btn-block text-danger" (click)="logout()">
            <i class="fa-solid fa-power-off"></i> <span>Cerrar Sesión</span>
          </button>
        </div>
      </aside>

      <!-- CONTENIDO PRINCIPAL -->
      <main class="content-wrapper">
        <!-- TOP NAVBAR -->
        <header class="top-navbar">
          <div class="page-title">
            <h1>{{ pageTitle }}</h1>
          </div>
          <div class="top-navbar-actions">
            <div class="api-status-badge" [ngClass]="dbConnected ? 'success' : 'error'">
              <i class="fa-solid fa-database"></i> <span>{{ dbConnected ? 'BD Conectada' : 'BD Desconectada' }}</span>
            </div>
            <div class="user-profile">
              <div class="avatar"><i class="fa-solid fa-user-gear"></i></div>
              <span>Administrador</span>
            </div>
          </div>
        </header>

        <!-- VISTAS CONTENEDOR -->
        <div class="views-container">
          <!-- VISTA: DASHBOARD -->
          <div *ngIf="activeTab === 'dashboard'" class="view active">
            <div class="grid-stats">
              <div class="stat-card p-purple">
                <div class="stat-icon"><i class="fa-solid fa-list-check"></i></div>
                <div class="stat-info">
                  <h3>Master Tramex</h3>
                  <p class="stat-number">{{ counts['master_tramex'] }}</p>
                </div>
              </div>
              <div class="stat-card p-blue">
                <div class="stat-icon"><i class="fa-solid fa-globe"></i></div>
                <div class="stat-info">
                  <h3>Global Entry</h3>
                  <p class="stat-number">{{ counts['global_entry'] }}</p>
                </div>
              </div>
              <div class="stat-card p-teal">
                <div class="stat-icon"><i class="fa-solid fa-book-bookmark"></i></div>
                <div class="stat-info">
                  <h3>Pasaportes</h3>
                  <p class="stat-number">{{ counts['pasaportes'] }}</p>
                </div>
              </div>
              <div class="stat-card p-orange">
                <div class="stat-icon"><i class="fa-solid fa-map"></i></div>
                <div class="stat-info">
                  <h3>Canadá</h3>
                  <p class="stat-number">{{ counts['canada'] }}</p>
                </div>
              </div>
            </div>

            <div class="dashboard-banner">
              <div class="banner-content">
                <h2>Bienvenido al Sistema de Gestión Tramex</h2>
                <p>Has reemplazado exitosamente el uso de archivos Excel por una solución centralizada y segura en PostgreSQL. Toda la información sensible como contraseñas de trámites se almacena cifrada en reposo y solo puede ser visualizada temporalmente por usuarios autenticados.</p>
              </div>
              <div class="banner-ill">
                <i class="fa-solid fa-shield-halved"></i>
              </div>
            </div>
          </div>

          <!-- VISTA: CRUD -->
          <div *ngIf="activeTab !== 'dashboard'" class="view active">
            <div class="crud-actions-bar">
              <div class="search-box">
                <i class="fa-magnifying-glass fa-solid"></i>
                <input type="text" placeholder="Buscar por nombre..." [(ngModel)]="searchQuery" (input)="onSearch()">
              </div>
              <button class="btn-primary" (click)="openAddModal()">
                <i class="fa-solid fa-plus"></i> <span>Agregar Registro</span>
              </button>
            </div>

            <!-- TABLA -->
            <div class="table-container">
              <table>
                <thead>
                  <tr>
                    <th *ngFor="let header of activeConfig.headers">{{ header }}</th>
                  </tr>
                </thead>
                <tbody>
                  <tr *ngIf="loadingData">
                    <td [attr.colspan]="activeConfig.headers.length" class="text-center">
                      <i class="fa-solid fa-spinner fa-spin"></i> Cargando información...
                    </td>
                  </tr>
                  <tr *ngIf="!loadingData && items.length === 0">
                    <td [attr.colspan]="activeConfig.headers.length" class="text-muted text-center">
                      No se encontraron trámites registrados.
                    </td>
                  </tr>
                  <tr *ngFor="let item of items">
                    <ng-container [ngSwitch]="activeTab">
                      <!-- Renderizar según el recurso activo -->
                      <ng-container *ngSwitchCase="'master_tramex'">
                        <td>{{ item.id }}</td>
                        <td><strong>{{ item.nombre }}</strong></td>
                        <td><span class="badge-mono">{{ item.id_solicitud || '-' }}</span></td>
                        <td>{{ item.telefono || '-' }}</td>
                        <td>{{ item.numero_pasaporte || '-' }}</td>
                        <td>{{ item.tramite || '-' }}</td>
                        <td>{{ item.cita || '-' }}</td>
                        <td>{{ item.correo_electronico || '-' }}</td>
                        <td>{{ formatDate(item.cargado_en) }}</td>
                      </ng-container>
                      <ng-container *ngSwitchCase="'global_entry'">
                        <td>{{ item.id }}</td>
                        <td><strong>{{ item.nombre }}</strong></td>
                        <td>{{ item.apellido || '-' }}</td>
                        <td>{{ item.correo_electronico || '-' }}</td>
                        <td>{{ item.numero_pasaporte || '-' }}</td>
                        <td>{{ formatDate(item.cargado_en) }}</td>
                      </ng-container>
                      <ng-container *ngSwitchCase="'pasaportes'">
                        <td>{{ item.id }}</td>
                        <td><strong>{{ item.nombre }}</strong></td>
                        <td>{{ item.apellido || '-' }}</td>
                        <td>{{ item.telefono || '-' }}</td>
                        <td>{{ item.lugar_cita || '-' }}</td>
                        <td>{{ item.fecha_cita || '-' }}</td>
                        <td><span class="text-muted">{{ item.fecha_cita_original || '-' }}</span></td>
                        <td>{{ formatDate(item.cargado_en) }}</td>
                      </ng-container>
                      <ng-container *ngSwitchCase="'canada'">
                        <td>{{ item.id }}</td>
                        <td><strong>{{ item.nombre }}</strong></td>
                        <td>{{ item.cuenta_ircc || '-' }}</td>
                        <td>{{ item.telefono || '-' }}</td>
                        <td>{{ item.numero_pasaporte || '-' }}</td>
                        <td>{{ formatDate(item.cargado_en) }}</td>
                      </ng-container>
                    </ng-container>
                    
                    <!-- Acciones -->
                    <td>
                      <div class="table-actions">
                        <button *ngIf="hasPassword()" class="btn-icon text-secondary" (click)="viewPassword(item.id)" title="Ver Contraseña">
                          <i class="fa-solid fa-key"></i>
                        </button>
                        <button class="btn-icon" (click)="openEditModal(item)" title="Editar">
                          <i class="fa-solid fa-pen-to-square"></i>
                        </button>
                        <button class="btn-icon danger" (click)="confirmDelete(item.id)" title="Eliminar">
                          <i class="fa-solid fa-trash-can"></i>
                        </button>
                      </div>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>

            <!-- PAGINACIÓN -->
            <div class="pagination-bar">
              <span class="pagination-info">Mostrando {{ getStartRange() }} a {{ getEndRange() }} de {{ totalRecords }} registros</span>
              <div class="pagination-controls">
                <button class="btn-icon" [disabled]="skip === 0" (click)="prevPage()"><i class="fa-solid fa-chevron-left"></i></button>
                <button class="btn-icon" [disabled]="getEndRange() >= totalRecords" (click)="nextPage()"><i class="fa-solid fa-chevron-right"></i></button>
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>

    <!-- =======================================================================
         MODALES
         ======================================================================= -->

    <!-- MODAL AGREGAR/EDITAR -->
    <div class="modal" [ngClass]="{'active': showRecordModal}">
      <div class="modal-content">
        <div class="modal-header">
          <h2>{{ isEditing ? 'Editar Registro #' + activeId : 'Agregar a ' + activeConfig.title }}</h2>
          <button type="button" class="btn-close-modal" (click)="closeModals()"><i class="fa-solid fa-xmark"></i></button>
        </div>
        <form (submit)="saveRecord($event)">
          <div class="modal-grid-fields">
            <div *ngFor="let field of activeConfig.fields" class="form-group" [ngClass]="{'grid-col-2': field.grid}">
              <label [for]="'f-' + field.name">{{ field.label }}</label>
              
              <ng-container *ngIf="field.type === 'password'; else standardField">
                <div class="password-input-wrapper">
                  <input [type]="showModalPassword ? 'text' : 'password'" [id]="'f-' + field.name]" [name]="field.name]" [(ngModel)]="formValues[field.name]" [placeholder]="isEditing ? 'Dejar vacío para no cambiar' : 'Contraseña de la cuenta'">
                  <button type="button" class="btn-toggle-pwd" (click)="toggleModalPassword()">
                    <i class="fa-solid" [ngClass]="showModalPassword ? 'fa-eye-slash' : 'fa-eye'"></i>
                  </button>
                </div>
              </ng-container>
              
              <ng-template #standardField>
                <input [type]="field.type" [id]="'f-' + field.name" [name]="field.name" [(ngModel)]="formValues[field.name]" [required]="!!field.required">
              </ng-template>
            </div>
          </div>
          <div class="modal-footer">
            <button type="button" class="btn-secondary" (click)="closeModals()">Cancelar</button>
            <button type="submit" class="btn-primary">Guardar</button>
          </div>
        </form>
      </div>
    </div>

    <!-- MODAL VER CONTRASEÑA -->
    <div class="modal" [ngClass]="{'active': showPasswordModal}">
      <div class="modal-content modal-sm">
        <div class="modal-header">
          <h2>Contraseña del Trámite</h2>
          <button type="button" class="btn-close-modal" (click)="closeModals()"><i class="fa-solid fa-xmark"></i></button>
        </div>
        <div class="modal-body">
          <p class="pwd-instruction">Esta contraseña viaja cifrada con AES-128. Aquí se muestra descifrada temporalmente:</p>
          <div class="decrypted-pwd-box">
            <span id="decrypted-pwd-text">{{ decryptedPassword }}</span>
            <button type="button" id="btn-copy-pwd" title="Copiar contraseña" (click)="copyPassword()">
              <i class="fa-regular fa-copy"></i>
            </button>
          </div>
        </div>
        <div class="modal-footer">
          <button type="button" class="btn-primary btn-close-modal btn-block" (click)="closeModals()">Entendido</button>
        </div>
      </div>
    </div>

    <!-- MODAL ELIMINAR -->
    <div class="modal" [ngClass]="{'active': showDeleteModal}">
      <div class="modal-content modal-sm">
        <div class="modal-header header-danger">
          <h2>Confirmar Eliminación</h2>
          <button type="button" class="btn-close-modal" (click)="closeModals()"><i class="fa-solid fa-xmark"></i></button>
        </div>
        <div class="modal-body">
          <p>¿Estás seguro de que deseas eliminar permanentemente este trámite?</p>
          <p class="text-danger-sub">Esta acción es irreversible y afectará la base de datos.</p>
        </div>
        <div class="modal-footer">
          <button type="button" class="btn-secondary" (click)="closeModals()">Cancelar</button>
          <button type="button" class="btn-danger" (click)="deleteRecord()">Eliminar</button>
        </div>
      </div>
    </div>

    <!-- NOTIFICACIONES (TOASTS) -->
    <div id="toast-container">
      <div *ngFor="let toast of toasts" class="toast {{ toast.type }}">
        <i class="fa-solid" [ngClass]="getToastIcon(toast.type)"></i>
        <span>{{ toast.message }}</span>
      </div>
    </div>
  `,
  styles: []
})
export class DashboardComponent implements OnInit {
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

  constructor(
    private api: ApiService,
    private auth: AuthService,
    private router: Router
  ) {}

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
