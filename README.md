# 📚 Sistema de Gestión de Biblioteca (MySQL)

Este proyecto es un sistema completo de gestión de bibliotecas que utiliza **MySQL** como base de datos relacional, con un backend en **Flask** y un frontend en **HTML/CSS/JavaScript**.

---

## 🌟 Características principales

- ✅ Interfaz intuitiva con pestañas para cada módulo
- 📘 Gestión completa de libros, ejemplares, usuarios, préstamos y reservas
- 🔁 Sistema de historial que registra todas las operaciones
- 🔍 Filtros avanzados por módulo
- ✅ Validación de datos tanto en cliente como en servidor
- 🔐 Transacciones ACID para operaciones críticas
- 🧾 Respaldo de datos mediante historial

---

## 🧰 Tecnologías utilizadas

### 🔧 Backend
- **Flask** – Microframework web para Python
- **Flask-CORS** – CORS para permitir solicitudes entre dominios
- **MySQL Connector** – Cliente para conexión a base de datos MySQL

### 🎨 Frontend
- **HTML5** – Estructura semántica
- **CSS3** – Estilos y diseño responsive
- **JavaScript (Vanilla)** – Lógica de cliente
- **Fetch API** – Comunicación con el backend

### 🗃️ Base de datos
- **MySQL** – Sistema de gestión relacional
- **Transacciones** – Integridad en operaciones críticas
- **JOINs** – Relaciones entre tablas

---

## 📁 Estructura del proyecto

```
biblioteca/
│
├── formulario.html       # Interfaz principal (Frontend)
├── editar.html           # Página para edición de registros
├── formulario.py         # Backend Flask (API REST)
└── estilo.css            # Estilos personalizados
```

---

## ⚙️ Instalación y configuración

### 1. Requisitos
- Python 3.7+
- MySQL Server instalado y corriendo
- pip (gestor de paquetes de Python)

### 2. Instalar dependencias
```bash
pip install flask flask-cors mysql-connector-python
```

### 3. Configurar MySQL
- Crear la base de datos `biblioteca`
- Ajustar credenciales en `formulario.py` (función `create_connection`)
- Ejecutar el script SQL para crear las tablas (ver más abajo)

### 4. Ejecutar el servidor
```bash
python formulario.py
```

### 5. Acceder a la aplicación
Abre tu navegador en: `http://localhost:5000/formulario.html`

---

## 🧩 Diagrama de casos de uso

Puedes agregar aquí un diagrama visual del sistema para entender mejor las funcionalidades:

![Diagrama de casos de uso](formulario_biblioteca/docs/diagrama-casos-de-uso.png)


---

## 🛠️ Estructura de base de datos (SQL)

> Este script crea las tablas necesarias para el sistema:

```sql
-- Ver estructura en la sección original 
CREATE DATABASE biblioteca;
CREATE DATABASE biblioteca;

USE biblioteca;

CREATE TABLE libros (
    id INT AUTO_INCREMENT PRIMARY KEY,
    titulo VARCHAR(255) NOT NULL,
    autor VARCHAR(255) NOT NULL,
    paginas INT NOT NULL,
    editorial VARCHAR(255) NOT NULL
);

CREATE TABLE ejemplares (
    id INT AUTO_INCREMENT PRIMARY KEY,
    numero_total INT NOT NULL,
    ejemplares_prestados INT DEFAULT 0,
    estado ENUM('available', 'borrowed', 'reserved') DEFAULT 'available',
    id_libro INT NOT NULL,
    titulo_libro VARCHAR(255),
    FOREIGN KEY (id_libro) REFERENCES libros(id)
);

CREATE TABLE usuarios (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(255) NOT NULL,
    correo VARCHAR(255) NOT NULL,
    telefono VARCHAR(20) NOT NULL,
    ejemplares_prestados INT DEFAULT 0,
    tiene_reserva BOOLEAN DEFAULT FALSE
);

CREATE TABLE prestamos (
    id INT AUTO_INCREMENT PRIMARY KEY,
    id_ejemplar INT NOT NULL,
    id_usuario INT NOT NULL,
    fecha_recibido DATE NOT NULL,
    fecha_debe_entregar DATE NOT NULL,
    fecha_entrega DATE,
    estado ENUM('borrowed', 'returned') DEFAULT 'borrowed',
    estado_libro ENUM('bueno', 'malgastado', 'dañado', 'perdido'),
    FOREIGN KEY (id_ejemplar) REFERENCES ejemplares(id),
    FOREIGN KEY (id_usuario) REFERENCES usuarios(id)
);

CREATE TABLE reservas (
    id INT AUTO_INCREMENT PRIMARY KEY,
    id_usuario INT NOT NULL,
    id_libro INT NOT NULL,
    id_ejemplar INT,
    fecha_solicitud DATE NOT NULL,
    estado ENUM('pending', 'completed', 'cancelled') DEFAULT 'pending',
    FOREIGN KEY (id_usuario) REFERENCES usuarios(id),
    FOREIGN KEY (id_libro) REFERENCES libros(id),
    FOREIGN KEY (id_ejemplar) REFERENCES ejemplares(id)
);

CREATE TABLE historial (
    id INT AUTO_INCREMENT PRIMARY KEY,
    accion ENUM('prestamo', 'devolucion', 'reserva') NOT NULL,
    id_ejemplar INT,
    id_usuario INT,
    id_prestamo INT,
    id_libro INT,
    fecha DATETIME DEFAULT CURRENT_TIMESTAMP,
    datos_adicionales TEXT,
    FOREIGN KEY (id_ejemplar) REFERENCES ejemplares(id),
    FOREIGN KEY (id_usuario) REFERENCES usuarios(id),
    FOREIGN KEY (id_prestamo) REFERENCES prestamos(id),
    FOREIGN KEY (id_libro) REFERENCES libros(id)
);
```

---

## 🔌 Endpoints principales

### Libros
- `GET /libros`
- `POST /add_libro`
- `PUT /libros/<id>`
- `DELETE /libros/<id>`

### Ejemplares
- `GET /ejemplares`
- `POST /add_ejemplar`

### Usuarios
- `GET /usuarios`
- `POST /add_usuario`

### Préstamos
- `POST /add_prestamo`
- `POST /devolver_prestamo/<id>`

### Reservas
- `POST /add_reserva`

### Historial
- `GET /historial`

---

## 🔄 Ejemplo de flujo de préstamo (JavaScript)

```javascript
document.getElementById('form-prestamo').addEventListener('submit', async function(e) {
  e.preventDefault();
  const formData = new FormData(this);
  try {
    const response = await fetch('http://localhost:5000/add_prestamo', {
      method: 'POST',
      body: formData
    });
    if (!response.ok) throw new Error('Error al registrar préstamo');
    alert('Préstamo registrado correctamente');
    this.reset();
    cargarDatos('Prestamos');
  } catch (error) {
    alert('Error: ' + error.message);
  }
});
```

---

## 🤝 Contribución

¡Las contribuciones son bienvenidas!

1. Haz un **fork** del repositorio
2. Crea una rama:
   ```bash
   git checkout -b feature/nueva-funcionalidad
   ```
3. Realiza cambios y haz commit:
   ```bash
   git commit -m "Añade nueva funcionalidad"
   ```
4. Push a tu rama:
   ```bash
   git push origin feature/nueva-funcionalidad
   ```
5. Abre un **Pull Request** 🚀

---

## 📄 Licencia

Este proyecto está bajo la **Licencia MIT**. Consulta el archivo `LICENSE` para más detalles.

---

## 📬 Contacto

¿Dudas o sugerencias? Hecho con ❤️ por Daniel Lozano  
📧 Correo: daniellozanocuervo@gmail.com  
🌐 GitHub: [Danielle2101](https://github.com/Danielle2101)
```
