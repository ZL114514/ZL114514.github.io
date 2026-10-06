@echo off
rem Telegram -> 博客 自动同步（Windows 计划任务每 6 小时调用；日志 scripts\.sync.log）
"C:\Program Files\Git\bin\bash.exe" -lc "/c/Users/ZL/Documents/ZL114514.github.io/scripts/sync-and-publish.sh"
