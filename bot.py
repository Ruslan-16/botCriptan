import requests

YANDEX_DISK_TOKEN = 'ВАШ_ТОКЕН_ЯНДЕКС_ДИСКА'
YDB_URL = "https://cloud-api.yandex.net/v1/disk/resources"
headers = {'Authorization': f'OAuth {YANDEX_DISK_TOKEN}'}

# Проверка подключения
response = requests.get(YDB_URL, headers=headers)
if response.status_code == 200:
    print("Токен работает! Подключение к Яндекс.Диску успешно.")
else:
    print(f"Ошибка подключения к Яндекс.Диску: {response.status_code}")
