TP1 Redes - File Transfer

levantar servidor: python3 start-server.py -H 127.0.0.1 -p 5000

levantar upload: python3 upload.py -H 127.0.0.1 -p 5000 -s <file_path> -n <file_name> 

    con selective_repeat : python3 upload.py -H 127.0.0.1 -p 5000 -s <file_path> -n <file_name>  -r selective-repeat

    con stop and wait:  python3 upload.py -H 127.0.0.1 -p 5000 -s <file_path> -n <file_name> -r stop-and-wait

levantar upload: python3 upload.py -H 127.0.0.1 -p 5000 -s <file_path> -n <file_name>

levantar download: python3 download.py -H 127.0.0.1 -p 5000 -n <file_name_on_server> -d <local_destination_path>

