-- recreate inventory database and tables
DROP DATABASE IF EXISTS inventario;
CREATE DATABASE IF NOT EXISTS inventario;
USE inventario;

-- Tabla de Proveedores
CREATE TABLE IF NOT EXISTS Proveedores (
 id_proveedor INT AUTO_INCREMENT,
 nombre VARCHAR(100) NOT NULL,
 direccion VARCHAR(255),
 telefono VARCHAR(20),
 email VARCHAR(100),
 constraint proveedorespk PRIMARY KEY (id_proveedor)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Tabla de Productos
CREATE TABLE IF NOT EXISTS Productos (
 id_producto INT AUTO_INCREMENT,
 nombre VARCHAR(100) NOT NULL,
 descripcion TEXT,
 precio_compra DECIMAL(10, 2) NOT NULL,
 porcentaje_ganancia DECIMAL(5, 2) NOT NULL,
 precio_venta DECIMAL(10, 2),
 stock INT NOT NULL,
 stock_minimo INT NOT NULL,
 id_proveedor INT,
 CONSTRAINT productopk PRIMARY KEY (id_producto),
 CONSTRAINT fk_proveedor FOREIGN KEY (id_proveedor)
    REFERENCES Proveedores(id_proveedor)
    ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Tabla de Clientes
CREATE TABLE IF NOT EXISTS Clientes (
 id_cliente INT AUTO_INCREMENT,
 nombre VARCHAR(100) NOT NULL,
 direccion VARCHAR(255),
 telefono VARCHAR(20),
 email VARCHAR(100),
 CONSTRAINT clientepk PRIMARY KEY (id_cliente)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Tabla de Ventas
CREATE TABLE IF NOT EXISTS Ventas (
 id_venta INT AUTO_INCREMENT,
 fecha_venta DATE NOT NULL,
 id_cliente INT,
 total DECIMAL(10, 2) NOT NULL,
 CONSTRAINT ventaspk PRIMARY KEY (id_venta),
 CONSTRAINT fk_cliente FOREIGN KEY (id_cliente)
    REFERENCES Clientes(id_cliente)
    ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Tabla Detalle de Ventas
CREATE TABLE IF NOT EXISTS Detalle_Ventas (
 id_detalle INT AUTO_INCREMENT,
 id_venta INT,
 id_producto INT,
 cantidad INT NOT NULL,
 precio_unitario DECIMAL(10, 2) NOT NULL,
 PRIMARY KEY (id_detalle),
 CONSTRAINT fk_venta FOREIGN KEY (id_venta)
    REFERENCES Ventas(id_venta)
    ON DELETE CASCADE,
 CONSTRAINT fk_producto FOREIGN KEY (id_producto)
    REFERENCES Productos(id_producto)
    ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Tabla de Usuarios
CREATE TABLE IF NOT EXISTS Usuarios (
 id_usuario INT AUTO_INCREMENT,
 username VARCHAR(50) NOT NULL,
 password VARCHAR(255) NOT NULL,
 rol ENUM('administrador', 'vendedor') NOT NULL,
 CONSTRAINT usuariopk PRIMARY KEY (id_usuario)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Tabla de Compras
CREATE TABLE IF NOT EXISTS Compras (
 id_compra INT AUTO_INCREMENT,
 id_proveedor INT,
 fecha_compra DATE NOT NULL,
 total DECIMAL(10, 2) NOT NULL,
 CONSTRAINT compraspk PRIMARY KEY (id_compra),
 CONSTRAINT fk_proveedor_compra FOREIGN KEY (id_proveedor)
    REFERENCES Proveedores(id_proveedor)
    ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Tabla Detalle de Compras
CREATE TABLE IF NOT EXISTS Detalle_Compras (
 id_detalle_compra INT AUTO_INCREMENT,
 id_compra INT,
 id_producto INT,
 cantidad INT NOT NULL,
 precio_compra DECIMAL(10, 2) NOT NULL,
 CONSTRAINT detallecomprapk PRIMARY KEY (id_detalle_compra),
 CONSTRAINT fk_compra FOREIGN KEY (id_compra)
    REFERENCES Compras(id_compra)
    ON DELETE CASCADE,
 CONSTRAINT fk_producto_compra FOREIGN KEY (id_producto)
    REFERENCES Productos(id_producto)
    ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
