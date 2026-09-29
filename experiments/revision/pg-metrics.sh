#!/bin/sh
# Bound to loopback inside the isolated study pod.
while IFS= read -r line; do
  [ "$line" = "$(printf '\r')" ] && break
done
body=$(printf 'UPTIME\n'; cat /proc/uptime
       printf 'CPU\n'; cat /sys/fs/cgroup/cpu.stat
       printf 'MEMORY\n'; cat /sys/fs/cgroup/memory.current
       printf 'IO\n'; cat /sys/fs/cgroup/io.stat)
length=$(printf '%s' "$body" | wc -c)
printf 'HTTP/1.0 200 OK\r\nContent-Type: text/plain\r\nContent-Length: %s\r\nConnection: close\r\n\r\n%s' "$length" "$body"
