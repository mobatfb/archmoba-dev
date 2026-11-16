-- KOF ARENA | Telemetria de vida para MAME 0.289 / kf2k2mp2
-- Lectura unicamente. No escribe RAM, no aplica cheats y no decide ganador.
-- Lanzar: mame.exe kf2k2mp2 -autoboot_script "KOF_Salud_MAME289.lua"
-- El anfitrion establece KOF_ARENA_LUA_STATE con la ruta de salida local.

local output_path = os.getenv("KOF_ARENA_LUA_STATE")
if not output_path or output_path == "" then
    output_path = "KOF_ARENA_LUA_ESTADO.txt"
end

local cpu = manager.machine.devices[":maincpu"]
if cpu == nil then
    emu.print_error("KOF ARENA Lua: falta :maincpu (usa kf2k2mp2).")
    return
end
local program = cpu.spaces["program"]
if program == nil then
    emu.print_error("KOF ARENA Lua: falta espacio de memoria program.")
    return
end

-- Direcciones de la RAM 68k del propio juego, encontradas en kf2k2mp2.ini.
local P1_HP = 0x108239
local P2_HP = 0x108439
-- Etiquetas del cheat: 'Rounds Lost'. Observacion, no resultado confirmado.
local P1_LOST = 0x10A7E5
local P2_LOST = 0x10A80B

local frames = 0
local seq = 0
local last_values = nil
local last_write_frame = -100
local warned_write = false
local warned_read = false

local function sample()
    return program:read_u8(P1_HP), program:read_u8(P2_HP),
           program:read_u8(P1_LOST), program:read_u8(P2_LOST)
end

local function write_state(p1, p2, l1, l2)
    seq = seq + 1
    local line = string.format("KOF_LUA_V1\t%d\t%d\t%d\t%d\t%d\n",
                               seq, p1, p2, l1, l2)
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

-- Conservar la suscripcion globalmente evita desactivaciones por GC.
_G.kof_arena_health_subscription = emu.add_machine_frame_notifier(function()
    frames = frames + 1
    -- 10 lecturas por segundo aprox.; actividad de disco solo si cambian
    -- los valores o cada 30 fotogramas para mantener una senal de vida.
    if frames % 6 ~= 0 then
        return
    end
    local ok, p1, p2, l1, l2 = pcall(sample)
    if not ok then
        if not warned_read then
            emu.print_error("KOF ARENA Lua: fallo al leer RAM: " .. tostring(p1))
            warned_read = true
        end
        return
    end
    warned_read = false
    local values = string.format("%d,%d,%d,%d", p1, p2, l1, l2)
    if values ~= last_values or frames - last_write_frame >= 30 then
        write_state(p1, p2, l1, l2)
        last_values = values
    end
end)

_G.kof_arena_reset_subscription = emu.add_machine_reset_notifier(function()
    last_values = nil
end)

emu.print_info("KOF ARENA Lua activo (SOLO LECTURA): " .. output_path)
