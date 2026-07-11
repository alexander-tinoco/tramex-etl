# Diagramas del Backend - Tramex API

Esta guía gráfica explica el funcionamiento interno del backend desarrollado con FastAPI, cubriendo la arquitectura, autenticación y seguridad de datos.

---

## 1. Arquitectura del Backend
Este diagrama muestra cómo viajan las solicitudes HTTP del cliente, cruzando los middlewares de CORS, validando el token de seguridad y enrutándose a los modelos ORM y la base de datos PostgreSQL.

```mermaid
graph TD
    Client[Cliente / Frontend] -->|HTTP Request| FastAPI[FastAPI App]
    FastAPI --> CORS[Middleware CORS]
    CORS --> AuthDep{get_current_user}
    
    subgraph Rutas ["Routers de la API"]
        AuthRouter["auth.py /token (Público)"]
        MasterRouter["master_tramex.py (Protegido)"]
        GERouter["global_entry.py (Protegido)"]
        PassRouter["pasaportes.py (Protegido)"]
        CanRouter["canada.py (Protegido)"]
    end
    
    FastAPI --> AuthRouter
    AuthDep -->|Si el Token es Válido| MasterRouter & GERouter & PassRouter & CanRouter
    
    subgraph Persistencia ["Capa de Persistencia"]
        Models[Modelos SQLAlchemy]
        DB[(PostgreSQL)]
    end
    
    MasterRouter & GERouter & PassRouter & CanRouter --> Models
    Models --> DB
```

---

## 2. Flujo de Autenticación JWT (Secuencia)
Describe el proceso que sigue el cliente para iniciar sesión con su nombre de usuario y contraseña (definidos en variables de entorno) y obtener un token JWT firmado de corta duración.

```mermaid
sequenceDiagram
    autonumber
    actor Cliente as Cliente (Frontend)
    participant Auth as Router de Autenticación
    participant Sec as Módulo de Seguridad
    
    Note over Cliente, Auth: Las credenciales viajan en formato Form URL-Encoded

    Cliente->>Auth: POST /api/auth/token (username, password)
    Auth->>Sec: Validar credenciales (con API_USERNAME / API_PASSWORD)
    alt Credenciales Correctas
        Sec-->>Auth: Credenciales Válidas
        Auth->>Sec: create_access_token({"sub": "username"})
        Sec-->>Auth: Retorna JWT firmado (expira en 24h)
        Auth-->>Cliente: HTTP 200 {"access_token": "eyJ...", "token_type": "bearer"}
    else Credenciales Incorrectas
        Sec-->>Auth: Credenciales Inválidas
        Auth-->>Cliente: HTTP 401 Unauthorized (WWW-Authenticate: Bearer)
    end
```

---

## 3. Flujo de Descifrado Seguro de Contraseñas (Secuencia)
Para proteger las contraseñas, los listados tradicionales (`GET /`) nunca las exponen. Este diagrama de secuencia detalla cómo funciona el endpoint específico para descifrar y retornar contraseñas únicamente a usuarios autenticados.

```mermaid
sequenceDiagram
    autonumber
    actor Cliente as Cliente (Autenticado)
    participant Route as Router (ej. /api/master-tramex)
    participant DB as PostgreSQL
    participant Crypt as Cryptography (Fernet)

    Cliente->>Route: GET /api/master-tramex/{id}/password (Headers: Authorization: Bearer <token>)
    Note over Route: La dependencia get_current_user valida el JWT
    alt Token Válido
        Route->>DB: Consultar registro por ID
        DB-->>Route: Retorna registro (contrasena_cifrada)
        Route->>Crypt: decrypt(contrasena_cifrada)
        Crypt-->>Route: Retorna contraseña plana ("SuperSecretPassword")
        Route-->>Cliente: HTTP 200 {"contrasena": "SuperSecretPassword"}
    else Token Inválido o Ausente
        Route-->>Cliente: HTTP 401 Unauthorized
    end
```
