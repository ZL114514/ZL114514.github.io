@echo off
rem 后台状态 -> 站点（轻量同步：不抓 TG，按 /admin 里的状态重排页面；计划任务每 10 分钟调用）
rem 日志与全量同步同一个：scripts\.sync.log
"C:\Program Files\Git\bin\bash.exe" -lc "/c/Users/ZL/Documents/ZL114514.github.io/scripts/sync-and-publish.sh --light"
