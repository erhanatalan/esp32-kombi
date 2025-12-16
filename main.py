import network, socket, time, dht, machine, ntptime
import ujson, gc, config
from machine import WDT

wdt = WDT(timeout=15000)

# ---------- WIFI ----------
wlan = network.WLAN(network.STA_IF)
wlan.active(True)

def wifi_connect():
    if not wlan.isconnected():
        wlan.connect(config.WIFI_SSID, config.WIFI_PASS)
        for _ in range(10):
            if wlan.isconnected():
                break
            time.sleep(1)

def wifi_check():
    if not wlan.isconnected():
        machine.reset()

wifi_connect()
try:
    ntptime.settime()
except:
    pass

# ---------- SENSOR ----------
sensor = dht.DHT22(machine.Pin(config.DHT_PIN))

def read_dht():
    try:
        sensor.measure()
        return round(sensor.temperature(),1), round(sensor.humidity(),1)
    except:
        return None, None

# ---------- TIME ----------
def is_day():
    h = time.localtime()[3]
    return config.DAY_START_HOUR <= h < config.DAY_END_HOUR

def decide(temp):
    if is_day():
        if temp < config.DAY_TEMP_MIN: return "OPEN"
        if temp > config.DAY_TEMP_MAX: return "CLOSE"
    else:
        if temp < config.NIGHT_TEMP_MIN: return "OPEN"
        if temp > config.NIGHT_TEMP_MAX: return "CLOSE"
    return "KEEP"

# ---------- CACHE ----------
cache = {
    "temperature": None,
    "humidity": None,
    "relay": "UNKNOWN",
    "timestamp": 0
}

last_read = 0

# ---------- SERVER ----------
addr = socket.getaddrinfo("0.0.0.0", config.SERVER_PORT)[0][-1]
s = socket.socket()
s.bind(addr)
s.listen(1)
s.settimeout(2)

print("ESP32 SERVER HAZIR")


# ---------- saat ----------

def get_time_hm():
    t = time.localtime()
    return "{:02d}:{:02d}".format(t[3], t[4])


# ---------- LOOP ----------
while True:
    wdt.feed()
    wifi_check()

    now = time.time()

    if now - last_read >= config.READ_INTERVAL:
        t, h = read_dht()
        if t is not None:
            cache.update({
                "temperature": t,
                "humidity": h,
                "relay": decide(t),
                "timestamp": get_time_hm()
            })
            print("CACHE:", cache)
        last_read = now

    try:
        conn, addr = s.accept()
        conn.settimeout(2)
        conn.recv(1024)
    except OSError:
        continue

    try:
        body = ujson.dumps(cache)
        conn.send("HTTP/1.1 200 OK\r\n")
        conn.send("Content-Type: application/json\r\n")
        conn.send("Connection: close\r\n")
        conn.send("Content-Length: {}\r\n\r\n".format(len(body)))
        conn.send(body)
    except:
        machine.reset()
    finally:
        conn.close()
        gc.collect()

