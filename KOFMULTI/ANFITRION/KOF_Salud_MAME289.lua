-- KOF ARENA | Telemetria de vida/KO para MAME 0.289, kf2k2mp2
-- Solo lectura de la RAM emulada. NO activa cheats ni entrega puntos.
-- El valor 254 fue observado por el usuario al morir un luchador.
-- El contador indica transiciones compatibles con KO, NO victorias de equipo.
local output_path = os.getenv("KOF_ARENA_LUA_STATE")
if not output_path or output_path == "" then
    output_path = "KOF_ARENA_LUA_ESTADO.txt"
end

local cpu = manager.machine.devices[":maincpu"]
if cpu == nil then
    emu.print_error("KOF ARENA Lua: falta :maincpu (kf2k2mp2).")
    return
end
local program = cpu.spaces["program"]
if program == nil then
    emu.print_error("KOF ARENA Lua: falta memoria program.")
    return
end

-- Direcciones INTERNAS Neo Geo, independientes del puntero Windows.
local P1_HP = 0x108239
local P2_HP = 0x108439
local P1_LOST = 0x10A7E5
local P2_LOST = 0x10A80B
local HP_KO = 254

local frames, seq = 0, 0
local last_values = nil
local last_write_frame = -100
local warned_write, warned_read = false, false
local ko_seen = {0, 0}
local last_health = {nil, nil}
local ready_frames = {0, 0}
local ko_armed = {false, false}
local saw_damage = {false, false}

local function sample()
    return program:read_u8(P1_HP), program:read_u8(P2_HP),
           program:read_u8(P1_LOST), program:read_u8(P2_LOST)
end

local function observe_character(player, hp)
    -- Evita contar 254 inicial del menu como KO. Se necesita haber visto
    -- vida normal durante varios fotogramas y posteriormente vida reducida.
    -- No rearmar con vida 0 durante la animacion de muerte.
    if hp >= 80 and hp <= 102 then
        ready_frames[player] = ready_frames[player] + 1
        if ready_frames[player] >= 5 then
            ko_armed[player] = true
        end
    else
        ready_frames[player] = 0
    end
    if ko_armed[player] and hp >= 0 and hp < 102 then
        saw_damage[player] = true
    end
    local detected = (hp == HP_KO and last_health[player] ~= HP_KO and
                      ko_armed[player] and saw_damage[player])
    if detected then
        ko_seen[player] = ko_seen[player] + 1
        ko_armed[player] = false
        saw_damage[player] = false
        ready_frames[player] = 0
    end
    last_health[player] = hp
    return detected
end

local function write_state(p1, p2, l1, l2)
    seq = seq + 1
    -- V2 agrega contadores de KO que permanecen aunque el siguiente
    -- personaje aparezca antes de que Python lea el archivo.
    local line = string.format("KOF_LUA_V2\t%d\t%d\t%d\t%d\t%d\t%d\t%d\n",
        seq, p1, p2, l1, l2, ko_seen[1], ko_seen[2])
    local file, err = io.open(output_path, "wb")
    if not file then
        if not warned_write then
            emu.print_error("KOF ARENA Lua: no puedo escribir telemetria: " ..
                            tostring(err))
            warned_write = true
        end
        return
    end
    file:write(line)
    file:close()
    warned_write = false
    last_write_frame = frames
end

-- Leemos 4 Bytes por fotograma, por si 254 dura muy poco tiempo.
-- Solo escribimos un archivo diminuto al cambiar valores / cada ~0.5s.
_G.kof_arena_health_subscription = emu.add_machine_frame_notifier(function()
    frames = frames + 1
    local ok, p1, p2, l1, l2 = pcall(sample)
    if not ok then
        if not warned_read then
            emu.print_error("KOF ARENA Lua: error leyendo RAM: " .. tostring(p1))
            warned_read = true
        end
        return
    end
    warned_read = false
    local ko_now = observe_character(1, p1) or false
    local ko_other = observe_character(2, p2) or false
    if frames % 6 ~= 0 and not ko_now and not ko_other then
        return
    end
    local values = string.format("%d,%d,%d,%d,%d,%d",
        p1, p2, l1, l2, ko_seen[1], ko_seen[2])
    if values ~= last_values or frames - last_write_frame >= 30 then
        write_state(p1, p2, l1, l2)
        last_values = values
    end
end)

_G.kof_arena_reset_subscription = emu.add_machine_reset_notifier(function()
    last_values = nil
    last_health = {nil, nil}
    ready_frames = {0, 0}
    ko_armed = {false, false}
    saw_damage = {false, false}
    -- Conservamos ko_seen desde que se abrio MAME: no es marcador por partida.
end)

emu.print_info("KOF ARENA Lua V2 activo (solo lectura): " .. output_path)
