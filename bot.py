import requests

YANDEX_DISK_TOKEN = 'y0_AgAAAABAMA6-AADLWwAAAAEW5PN-AABxGvuOh-1FNZdlYG16yhe5l_VWkw'
YDB_URL = "https://cloud-api.yandex.net/v1/disk/resources"
headers = {'Authorization': f'OAuth {YANDEX_DISK_TOKEN}'}

# Проверка подключения
response = requests.get(YDB_URL, headers=headers)
if response.status_code == 200:
    print("Токен работает! Подключение к Яндекс.Диску успешно.")
else:
    print(f"Ошибка подключения к Яндекс.Диску: {response.status_code}")
