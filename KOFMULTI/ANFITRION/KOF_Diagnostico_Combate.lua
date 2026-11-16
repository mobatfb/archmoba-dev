-- KOFMULTI | Diagnostico emulado por fotograma - kf2k2mp2 / MAME 0.289
-- SOLO LECTURA. No modifica RAM, tiempo, rondas ni puntuaciones.
-- Captura hp1/hp2, contadores, timer y bytes vecinos para analizar KO/equipo.
-- Arrancar desde KOF_Diagnostico_Combate.py o con -autoboot_script.

local state_path = os.getenv("KOF_DIAG_STATE") or "KOF_DIAG_ESTADO.tsv"
local events_path = os.getenv("KOF_DIAG_EVENTS") or "KOF_DIAG_EVENTOS.tsv"
local clips_path = os.getenv("KOF_DIAG_CLIPS") or "KOF_DIAG_CLIPS.tsv"
local commands_path = os.getenv("KOF_DIAG_COMMAND") or "KOF_DIAG_COMANDO.tsv"

local cpu = manager.machine.devices[":maincpu"]
if cpu == nil then
    emu.print_error("KOF_DIAG: no existe :maincpu.")
    return
end
local mem = cpu.spaces["program"]
if mem == nil then
    emu.print_error("KOF_DIAG: no existe memoria program.")
    return
end

local A = {
    hp1 = 0x108239, hp2 = 0x108439,
    lost1 = 0x10A7E5, lost2 = 0x10A80B,
    timer = 0x10A7D2, timer_aux = 0x10A7D3
}

local frame, seq, last_command_id = 0, 0, 0
local ko1, ko2 = 0, 0
local prev = nil
local last_state_frame = -60
local history, history_size, history_head, history_count = {}, 180, 1, 0
local clip_id, follow_frames = 0, 0
local warning = {}

local function report_error(what, detail)
    if not warning[what] then
        emu.print_error("KOF_DIAG " .. what .. ": " .. tostring(detail))
        warning[what] = true
    end
end

local function sample()
    return {
        hp1 = mem:read_u8(A.hp1),
        hp2 = mem:read_u8(A.hp2),
        lost1 = mem:read_u8(A.lost1),
        lost2 = mem:read_u8(A.lost2),
        timer = mem:read_u8(A.timer),
        timer_aux = mem:read_u8(A.timer_aux)
    }
end

local function one_line(s)
    return string.format("%d\t%d\t%d\t%d\t%d\t%d\t%d\t%d\t%d",
        frame, s.hp1, s.hp2, s.lost1, s.lost2, s.timer,
        s.timer_aux, ko1, ko2)
end

local function append_line(path, line)
    local file, err = io.open(path, "ab")
    if not file then
        report_error("archivo", err)
        return
    end
    file:write(line, "\n")
    file:close()
end

local function write_heartbeat(s)
    seq = seq + 1
    local file, err = io.open(state_path, "wb")
    if not file then
        report_error("estado", err)
        return
    end
    file:write("KOF_DIAG_STATE1\t", seq, "\t", one_line(s), "\n")
    file:close()
    last_state_frame = frame
end

local function dump_near(address)
    -- 32 bytes de contexto alrededor de cada referencia, todo de solo lectura.
    local parts = {}
    for delta = -16, 15 do
        local ok, value = pcall(function()
            return mem:read_u8(address + delta)
        end)
        parts[#parts + 1] = (ok and string.format("%02X", value)) or "??"
    end
    return table.concat(parts)
end

local function add_history(s)
    history[history_head] = {frame, s.hp1, s.hp2, s.lost1,
                            s.lost2, s.timer, s.timer_aux}
    history_head = history_head % history_size + 1
    history_count = math.min(history_count + 1, history_size)
end

local function clip_line(kind, item)
    return string.format("KOF_CLIP1\t%d\t%s\t%d\t%d\t%d\t%d\t%d\t%d\t%d",
        clip_id, kind, item[1], item[2], item[3],
        item[4], item[5], item[6], item[7])
end

local function start_clip()
    -- Copia los últimos 180 fotogramas y los 120 posteriores al evento.
    -- No pierde el instante del KO aunque desaparezca muy pronto.
    clip_id = clip_id + 1
    local start = ((history_head - 1 - history_count + history_size * 2)
                   % history_size) + 1
    local file, err = io.open(clips_path, "ab")
    if not file then
        report_error("clip", err)
        return
    end
    for n = 0, history_count - 1 do
        local index = ((start - 1 + n) % history_size) + 1
        file:write(clip_line("PRE", history[index]), "\n")
    end
    file:close()
    follow_frames = 120
end

local function event(kind, s, with_clip)
    -- Evento fechado en FOTOGRAMAS EMULADOS, no por el reloj de Windows.
    -- Adjunta 4 fragmentos de 32 bytes para analizar banderas vecinas.
    append_line(events_path, table.concat({
        "KOF_DIAG_EVT1", one_line(s), kind,
        dump_near(A.hp1), dump_near(A.hp2),
        dump_near(A.lost1), dump_near(A.lost2),
        dump_near(A.timer)
    }, "\t"))
    if with_clip then start_clip() end
end

local allowed_marks = {
    INICIO_COMBATE = true, KO_P1_CONFIRMADO = true,
    KO_P2_CONFIRMADO = true, CAMBIO_PERSONAJE_P1 = true,
    CAMBIO_PERSONAJE_P2 = true, FIN_EQUIPO_P1 = true,
    FIN_EQUIPO_P2 = true, TIEMPO_AGOTADO_CONFIRMADO = true,
    FIN_COMBATE = true, OBSERVACION = true
}

local function poll_command(s)
    if frame % 3 ~= 0 then return end
    local file = io.open(commands_path, "rb")
    if not file then return end
    local line = file:read("*l")
    file:close()
    if not line then return end
    local id_text, name = line:match("^KOF_DIAG_CMD1\t(%d+)\t([A-Z0-9_]+)$")
    local id = tonumber(id_text)
    if id and id > last_command_id and allowed_marks[name] then
        last_command_id = id
        event("MARCA_" .. name, s, true)
    end
end

-- Cada fotograma: no depender del refresco lento de la ventana Python.
_G.kof_diagnostic_frame_subscription = emu.add_machine_frame_notifier(function()
    frame = frame + 1
    local ok, s = pcall(sample)
    if not ok then
        report_error("lectura", s)
        return
    end

    -- Memoria del fotograma ACTUAL antes de emitir el clip.
    add_history(s)

    if prev then
        if s.hp1 == 254 and prev.hp1 ~= 254 then
            ko1 = ko1 + 1  -- 254 observado: posible KO, NO punto.
            event("P1_ENTRO_254", s, true)
        end
        if s.hp2 == 254 and prev.hp2 ~= 254 then
            ko2 = ko2 + 1
            event("P2_ENTRO_254", s, true)
        end
        if s.hp1 < prev.hp1 and s.hp1 <= 102 and prev.hp1 <= 102 then
            event("DAÑO_P1", s, false)
        end
        if s.hp2 < prev.hp2 and s.hp2 <= 102 and prev.hp2 <= 102 then
            event("DAÑO_P2", s, false)
        end
        if s.lost1 ~= prev.lost1 then
            event("CONTADOR_P1_CAMBIO", s, true)
        end
        if s.lost2 ~= prev.lost2 then
            event("CONTADOR_P2_CAMBIO", s, true)
        end
        if s.timer == 0 and prev.timer ~= 0 then
            event("TIEMPO_LLEGO_CERO", s, true)
        end
        if s.timer > prev.timer and s.timer - prev.timer >= 10 then
            event("TIEMPO_REINICIO_O_CAMBIO", s, false)
        end
        if s.timer_aux ~= prev.timer_aux then
            event("ESTADO_TIEMPO_CAMBIO", s, false)
        end
        if s.hp1 == 254 and s.lost1 >= 2 and
                not (prev.hp1 == 254 and prev.lost1 >= 2) then
            event("POSIBLE_FIN_EQUIPO_P1", s, true)
        end
        if s.hp2 == 254 and s.lost2 >= 2 and
                not (prev.hp2 == 254 and prev.lost2 >= 2) then
            event("POSIBLE_FIN_EQUIPO_P2", s, true)
        end
    end

    if follow_frames > 0 then
        follow_frames = follow_frames - 1
        append_line(clips_path, clip_line("POST", {
            frame, s.hp1, s.hp2, s.lost1, s.lost2, s.timer, s.timer_aux
        }))
    end

    poll_command(s)

    if frame % 6 == 0 or frame - last_state_frame >= 30 then
        write_heartbeat(s)
    end
    prev = s
end)

_G.kof_diagnostic_reset_subscription = emu.add_machine_reset_notifier(function()
    prev = nil
    history, history_head, history_count = {}, 1, 0
    follow_frames = 0
    -- Los contadores ko1/ko2 muestran eventos desde que se abrió MAME.
end)

emu.print_info("KOF_DIAG Lua activo. Registrando KO, fin de equipo y tiempo sin modificar RAM.")
