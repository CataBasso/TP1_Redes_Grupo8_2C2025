TP1 Redes - File Transfer

levantar servidor: python3 start-server.py -H 127.0.0.1 -p 5000

levantar upload: python3 upload.py -H 127.0.0.1 -p 5000 -s <file_path> -n <file_name>

    con selective_repeat : python3 upload.py -H 127.0.0.1 -p 5000 -s <file_path> -n <file_name>  -r selective-repeat

    con stop and wait:  python3 upload.py -H 127.0.0.1 -p 5000 -s <file_path> -n <file_name> -r stop-and-wait

levantar upload: python3 upload.py -H 127.0.0.1 -p 5000 -s <file_path> -n <file_name>

levantar download: python3 download.py -H 127.0.0.1 -p 5000 -n <file_name_on_server> -d <local_destination_path> 

las IPs 10.0.0.1 y 10.0.0.2 son las que se utilizan en xterm

levantar mininet:
> sudo mn --topo single,2 --link tc,loss=10

dentro de mininet ejecutar:
> xterm h1 h2 
 y se abren dos terminales\

despues en la terminal h1 levantas el server y en h2 el cliente con puerto 10.0.0.1 en ambos casos