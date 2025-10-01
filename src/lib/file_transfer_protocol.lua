-- Plugin para Wireshark
local file_transfer_proto = Proto("filetransfer_g8", "File Transfer Protocol - Grupo 8")

-- Campos para tu protocolo de texto
local fields = file_transfer_proto.fields
fields.message_type = ProtoField.string("filetransfer_g8.msg_type", "Message Type")
fields.protocol_type = ProtoField.string("filetransfer_g8.protocol", "Protocol")
fields.filename = ProtoField.string("filetransfer_g8.filename", "Filename")
fields.filesize = ProtoField.uint32("filetransfer_g8.filesize", "File Size")
fields.server_port = ProtoField.uint16("filetransfer_g8.port", "Server Port")
fields.error_msg = ProtoField.string("filetransfer_g8.error", "Error Message")
fields.status = ProtoField.string("filetransfer_g8.status", "Status")

function file_transfer_proto.dissector(buffer, pinfo, tree)
    local length = buffer:len()
    if length == 0 then return end
    
    local data = buffer():string()
    pinfo.cols.protocol = "FileTrans_G8"
    
    -- Parsear mensajes de tu protocolo real
    if string.match(data, "^UPLOAD_CLIENT:") then
        local parts = {}
        for part in string.gmatch(data, "([^:]+)") do
            table.insert(parts, part)
        end
        
        local subtree = tree:add(file_transfer_proto, buffer(), "Upload Request")
        subtree:add(fields.message_type, buffer(), parts[1] or "")
        subtree:add(fields.protocol_type, buffer(), parts[2] or "")
        subtree:add(fields.filename, buffer(), parts[3] or "")
        subtree:add(fields.filesize, buffer(), tonumber(parts[4]) or 0)
        subtree:add(fields.status, buffer(), "CLIENT_REQUEST")
        
        pinfo.cols.info = string.format("UPLOAD: %s (%s) [%s]", 
                                       parts[3] or "?", parts[4] or "?", parts[2] or "?")
        
    elseif string.match(data, "^DOWNLOAD_CLIENT:") then
        local parts = {}
        for part in string.gmatch(data, "([^:]+)") do
            table.insert(parts, part)
        end
        
        local subtree = tree:add(file_transfer_proto, buffer(), "Download Request")
        subtree:add(fields.message_type, buffer(), parts[1] or "")
        subtree:add(fields.protocol_type, buffer(), parts[2] or "")
        subtree:add(fields.filename, buffer(), parts[3] or "")
        subtree:add(fields.status, buffer(), "CLIENT_REQUEST")
        
        pinfo.cols.info = string.format("DOWNLOAD: %s [%s]", parts[3] or "?", parts[2] or "?")
        
    elseif string.match(data, "^UPLOAD_OK:") or string.match(data, "^DOWNLOAD_OK:") then
        local parts = {}
        for part in string.gmatch(data, "([^:]+)") do
            table.insert(parts, part)
        end
        
        local subtree = tree:add(file_transfer_proto, buffer(), "Server OK Response")
        subtree:add(fields.message_type, buffer(), parts[1] or "")
        subtree:add(fields.status, buffer(), "SERVER_ACCEPTED")
        
        if parts[2] then
            subtree:add(fields.server_port, buffer(), tonumber(parts[2]) or 0)
        end
        
        pinfo.cols.info = string.format("SERVER OK → Port %s", parts[2] or "?")
        
    elseif string.match(data, "ERROR") then
        local subtree = tree:add(file_transfer_proto, buffer(), "Server Error")
        subtree:add(fields.error_msg, buffer(), data)
        subtree:add(fields.status, buffer(), "SERVER_ERROR")
        pinfo.cols.info = "SERVER ERROR"
        
    else
        -- Datos del archivo o ACKs
        local subtree = tree:add(file_transfer_proto, buffer(), "Data/ACK Packet")
        pinfo.cols.info = string.format("DATA (%d bytes)", length)
    end
    
    return length
end

-- Heurística para TU protocolo
function file_transfer_proto.heuristic(buffer, pinfo, tree)
    if buffer:len() == 0 then return false end
    
    local data = buffer():string()
    
    -- Detectar TUS mensajes específicos
    if string.match(data, "^UPLOAD_CLIENT:") or
       string.match(data, "^DOWNLOAD_CLIENT:") or
       string.match(data, "^UPLOAD_OK:") or
       string.match(data, "^DOWNLOAD_OK:") or
       string.match(data, "ERROR") then
        file_transfer_proto.dissector(buffer, pinfo, tree)
        return true
    end
    
    return false
end

-- Registrar
file_transfer_proto:register_heuristic("udp", file_transfer_proto.heuristic)
local udp_port = DissectorTable.get("udp.port")
udp_port:add(8080, file_transfer_proto)