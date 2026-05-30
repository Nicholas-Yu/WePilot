#!/bin/bash
set -e

BOT_DIR="$(cd "$(dirname "$0")" && pwd)"
PID_FILE="$BOT_DIR/data/bot.pid"
LOG_FILE="$BOT_DIR/data/bot.log"

get_pid() {
    if [ -f "$PID_FILE" ]; then
        local pid
        pid=$(cat "$PID_FILE" 2>/dev/null)
        if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
            echo "$pid"
            return 0
        fi
    fi
    return 1
}

case "${1:-}" in
    start)
        pid=$(get_pid) && echo "机器人已在运行 (PID: $pid)" && exit 0
        echo "启动机器人..."
        cd "$BOT_DIR"
        nohup python3 bot.py >> "$LOG_FILE" 2>&1 &
        sleep 2
        pid=$(get_pid) && echo "启动成功 (PID: $pid)" || echo "启动失败，请查看日志: $LOG_FILE"
        ;;
    stop)
        pid=$(get_pid) || { echo "机器人未在运行"; exit 0; }
        echo "停止机器人 (PID: $pid)..."
        kill "$pid"
        sleep 2
        kill -0 "$pid" 2>/dev/null && kill -9 "$pid" 2>/dev/null
        rm -f "$PID_FILE"
        echo "已停止"
        ;;
    restart)
        $0 stop
        sleep 1
        $0 start
        ;;
    status)
        pid=$(get_pid) && echo "机器人运行中 (PID: $pid)" || echo "机器人未运行"
        ;;
    log)
        tail -f "$LOG_FILE"
        ;;
    *)
        echo "用法: $0 {start|stop|restart|status|log}"
        exit 1
        ;;
esac
