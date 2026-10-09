@echo off
rem light sync: re-render pages from cached state, no TG fetch (scheduled task, every 10 min)
rem log: scripts\.sync.log
"C:\Program Files\Git\bin\bash.exe" -lc "/c/Users/ZL/Documents/ZL114514.github.io/scripts/sync-and-publish.sh --light"
