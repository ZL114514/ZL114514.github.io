@echo off
rem full sync: Telegram -> blog (scheduled task, every 6 hours)
rem log: scripts\.sync.log
"C:\Program Files\Git\bin\bash.exe" -lc "/c/Users/ZL/Documents/ZL114514.github.io/scripts/sync-and-publish.sh"
