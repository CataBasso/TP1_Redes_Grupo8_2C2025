# TP1 Redes - File Transfer

## Servidor: 

```bash
> python start-server -h
```
> Usage: start-server [ -h ] [ -v | -q ] [ -H ADDR ] [ -p PORT ] [ -s DIRPATH ]

| Command/Option | Description |
|----------------|-------------|
| `-h, --help`   | Show this help message and exit |
| `-v, --verbose`| Increase output verbosity |
| `-q, --quiet`  | Decrease output verbosity |
| `-H, --host`   | Service IP address |
| `-p, --port`   | Service port |
| `-s, --storage`| Storage dir path |



## Cliente:
> Los unicos protocolos soportados son Stop and Wait y Selective Repeat, si no se especifica el protocolo deseado con la flag -r, se utilizara Stop and Wait por default.

### *Upload* 

```bash
> python upload -h
```
> Usage: upload [ -h ] [ -v | -q ] [ -H ADDR ] [ -p PORT ] [ -s FILEPATH ] [ -n FILENAME ] [ -r protocol ]

| Command/Option  | Description                       |
|-----------------|-----------------------------------|
| `-h, --help`    | Show this help message and exit   |
| `-v, --verbose` | Increase output verbosity         |
| `-q, --quiet`   | Decrease output verbosity         |
| `-H, --host`    | Server IP address                 |
| `-p, --port`    | Server port                       |
| `-s, --src`     | Source file path                  |
| `-n, --name`    | File name                         |
| `-r, --protocol`| Error recovery protocol           |


### *Download*

```bash
> python download -h
```
> Usage: download [ -h ] [ -v | -q ] [ -H ADDR ] [ -p PORT ] [ -d FILEPATH ] [ -n FILENAME ] [ -r protocol ]

| Command/Option   | Description                       |
|------------------|-----------------------------------|
| `-h, --help`     | Show this help message and exit   |
| `-v, --verbose`  | Increase output verbosity         |
| `-q, --quiet`    | Decrease output verbosity         |
| `-H, --host`     | Server IP address                 |
| `-p, --port`     | Server port                       |
| `-d, --dst`      | Destination file path             |
| `-n, --name`     | File name                         |
| `-r, --protocol` | Error recovery protocol           |

## Mininet

#### Para correr el programa con *Mininet* y verificar que los protocolos implementados garantizan la transmision a pesar de una posible perdida de paquetes con un porcentaje del 10%

```bash
# Instalar dependencias
sudo apt update && sudo apt upgrade -y
sudo apt install -y git vim python3 python3-pip

# Instalar mininet
sudo apt install mininet

# levantar mininet con con dos host, un switch y 10% de packet loss
sudo mn --topo single,2 --link tc,loss=10

# Adentro de mininet
mininet> xterm h1 h2
```
##### Al ejecutar esos comandos se abriran dos terminales de *xterm* h1 con ip 10.0.0.1 y h2 con ip 10.0.0.2, ya que son las default
> Levantar el servidor en h1 y el client como "upload" o "download" en h2
