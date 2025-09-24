# TP1 Redes - File Transfer

## Servidor: 

```bash
# Normal mode
python3 start-server.py -H 127.0.0.1 -p 5000

# Verbose mode
python3 start-server.py  -v -H 127.0.0.1 -p 5000

# Quiet mode
python3 start-server.py -q -H 127.0.0.1 -p 5000
```
## Cliente:
### *Upload* 
#### Si no se especifica " -r " el protocolo por default sera el 'Stop & Wait'

#### **Stop & Wait**
```bash
# Normal mode
python3 upload.py -H 127.0.0.1 -p 5000 -s <file_path> -n <file_name> -r stop-and-wait

# Verbose mode
python3 upload.py -v -H 127.0.0.1 -p 5000 -s <file_path> -n <file_name> -r stop-and-wait

# Quiet mode
python3 upload.py -q -H 127.0.0.1 -p 5000 -s <file_path> -n <file_name> -r stop-and-wait
```
#### **Selective Repeat**
```bash
# Normal mode
python3 upload.py -H 127.0.0.1 -p 5000 -s <file_path> -n <file_name> -r selective-repeat

# Verbose mode
python3 upload.py -v -H 127.0.0.1 -p 5000 -s <file_path> -n <file_name> -r selective-repeat

# Quiet mode
python3 upload.py -q -H 127.0.0.1 -p 5000 -s <file_path> -n <file_name> -r selective-repeat
```
### *Download*
#### **Stop & Wait**
```bash
# Normal mode
python3 download.py -H 127.0.0.1 -p 5000 -n <file_name_on_server> -d <local_destination_path> 

# Verbose mode
python3 download.py -v -H 127.0.0.1 -p 5000 -n <file_name_on_server> -d <local_destination_path> 

# Quiet mode
python3 download.py -q -H 127.0.0.1 -p 5000 -n <file_name_on_server> -d <local_destination_path> 
```
#### **Selective Repeat**
```bash
# Normal mode
python3 download.py -H 127.0.0.1 -p 5000 -n <file_name_on_server> -d <local_destination_path> -r selective-repeat

# Verbose mode
python3 download.py -v -H 127.0.0.1 -p 5000 -n <file_name_on_server> -d <local_destination_path> -r selective-repeat 

# Quiet mode
python3 download.py -q -H 127.0.0.1 -p 5000 -n <file_name_on_server> -d <local_destination_path> -r selective-repeat 
```

## Mininet

#### Para correr el programa con *Mininet* y verificar que los protocolos implementados garantizan la transmision a pesar de una posible perdida de paquetes con un porcentaje del 10%

```bash
# Instalar dependencias
sudo apt update && sudo apt upgrade -y
sudo apt install -y git vim python3 python3-pip

# Instalar mininet
sudo apt install mininet

# Abrir mininet
sudo mn --topo single,2 --link tc,loss=10

# Adentro de mininet
mininet > xterm h1 h2
```
##### Al ejecutar esos comandos se abriran dos terminales de *mininet*, y seguir los pasos anteriores para ejecutar tanto el servidor y el/los clientes cambiando los host a
- 10.0.0.1 ó 10.0.0.2
##### ya que son las que utiliza *xterm*
