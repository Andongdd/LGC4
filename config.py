# config.py
THRESHOLDS = {
    "OLED55C4":  999,   # 严格小于才触发
    "OLED65C4": 1300,
    "OLED55B4":  750,
    "OLED65B4":  850,
}

# 邮件发送配置（建议用环境变量）
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_USER = "@gmail.com"   
SMTP_PASS = "iilz vcqp twxw"        
MAIL_TO   = ["@outlook.com"]
MAIL_FROM = SMTP_USER
