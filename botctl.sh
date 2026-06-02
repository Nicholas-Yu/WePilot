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
        echo "启动机器人（防休眠模式）..."
        cd "$BOT_DIR"
        nohup caffeinate -dims python3 bot.py > /dev/null 2>&1 &
        sleep 2
        pid=$(get_pid) && echo "启动成功 (PID: $pid)" || echo "启动失败，请查看日志: $LOG_FILE"
        ;;
    stop)
        pid=$(get_pid) || { echo "机器人未在运行"; exit 0; }
        echo "停止机器人 (PID: $pid)..."
        kill "$pid"
        sleep 2
        kill -0 "$pid" 2>/dev/null && kill -9 "$pid" 2>/dev/null
        rm -f "$PID_FILE" "${PID_FILE%.pid}.lock"
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
    add)
        cd "$BOT_DIR"
        python3 bot.py --add
        ;;
    list)
        cd "$BOT_DIR"
        python3 bot.py --list
        ;;
    remove)
        if [ -z "${2:-}" ]; then
            echo "用法: $0 remove <账号ID>"
            echo "使用 '$0 list' 查看已配置的账号"
            exit 1
        fi
        cd "$BOT_DIR"
        python3 bot.py --remove "$2"
        ;;
    *)
        echo "用法: $0 {start|stop|restart|status|log|add|list|remove}"
        echo ""
        echo "  start    启动机器人（自动加载所有账号）"
        echo "  stop     停止机器人"
        echo "  restart  重启机器人"
        echo "  status   查看运行状态"
        echo "  log      查看实时日志"
        echo "  add      添加新微信账号（扫码登录）"
        echo "  list     列出所有已配置账号"
        echo "  remove   移除指定账号"
        exit 1
        ;;
esac
