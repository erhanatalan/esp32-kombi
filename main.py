import socket, time, dht, machine, ntptime
import ujson, gc, config
import secret
from machine import WDT

print("ESP32 SENSOR SERVER ÇALIŞIYOR")

wdt = WDT(timeout=15000)

UTC_OFFSET = 3 * 3600   # Türkiye

# ---------- TIME ----------
try:
    ntptime.settime()
except:
    pass

def get_time_hm():
    t = time.localtime(time.time() + UTC_OFFSET)
    return "{:02d}:{:02d}".format(t[3], t[4])

# ---------- SENSOR ----------
sensor = dht.DHT22(machine.Pin(config.DHT_PIN))

def read_dht():
    try:
        sensor.measure()
        return round(sensor.temperature(), 1), round(sensor.humidity(), 1)
    except:
        return None, None

# ---------- CACHE ----------
cache = {
    "temperature": None,
    "humidity": None,
    "timestamp": "00:00"
}

last_read = 0

# ---------- SERVER ----------
addr = socket.getaddrinfo("0.0.0.0", config.SERVER_PORT)[0][-1]
s = socket.socket()
s.bind(addr)
s.listen(1)
s.settimeout(2)

print("HTTP SERVER HAZIR")

# ---------- LOOP ----------
while True:
    wdt.feed()
    now = time.time()

    if now - last_read >= config.READ_INTERVAL:
        t, h = read_dht()
        if t is not None:
            cache.update({
                "temperature": t,
                "humidity": h,
                "timestamp": get_time_hm()
            })
            print("DATA:", cache)
        last_read = now

    try:
        conn, addr = s.accept()
        conn.recv(1024)
    except OSError:
        continue

    try:
        body = ujson.dumps(cache)
        conn.send(
            "HTTP/1.1 200 OK\r\n"
            "Content-Type: application/json\r\n"
            "Connection: close\r\n"
            "Content-Length: {}\r\n\r\n{}".format(len(body), body)
        )
    finally:
        conn.close()
        gc.collect()
