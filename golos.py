import time
import logging
import sys
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# Импорт конфигурации
try:
    import config
except ImportError:
    print("Ошибка: файл config.py не найден. Создайте его на основе config.example.py")
    sys.exit(1)

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('golos.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Конфигурация из config.py
URL = config.URL
LOGIN = config.LOGIN
PASSWORD = config.PASSWORD

# Селекторы на основе конфигурации
USERNAME_SELECTOR = (By.NAME, config.USERNAME_FIELD)
PASSWORD_SELECTOR = (By.NAME, config.PASSWORD_FIELD)
SUBMIT_SELECTOR = (By.XPATH, config.SUBMIT_BUTTON_XPATH)
BONUS_BUTTON_SELECTOR = (By.XPATH, f"//button[contains(@class, '{config.BONUS_BUTTON_CLASS}')]")

def click_bonus_button():
    """Нажимает кнопку бонуса на сайте."""
    logger.info("Запуск процесса нажатия кнопки бонуса")
    
    # Настройка браузера
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--window-size=1920,1080")  # Важно для headless
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36")
    
    # Для стабильности
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)

    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
    except Exception as e:
        logger.error(f"Ошибка при инициализации драйвера: {e}")
        return False
    
    try:
        # Открытие сайта
        logger.info(f"Открытие страницы: {URL}")
        driver.get(URL)
        
        # Авторизация
        try:
            logger.info("Попытка авторизации")
            WebDriverWait(driver, config.LOGIN_TIMEOUT).until(
                EC.element_to_be_clickable(USERNAME_SELECTOR)
            ).send_keys(LOGIN)
            
            driver.find_element(*PASSWORD_SELECTOR).send_keys(PASSWORD)
            driver.find_element(*SUBMIT_SELECTOR).click()
            logger.info("Авторизация выполнена")
            
            # Ожидание загрузки после авторизации
            time.sleep(config.DELAY_AFTER_LOGIN)
            
        except Exception as e:
            logger.error(f"Ошибка авторизации: {e}")
            driver.save_screenshot(f"auth_error_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
            return False
        
        # Обход блокировки кнопки
        try:
            driver.execute_script(f"""
                var buttons = document.querySelectorAll('button.{config.BONUS_BUTTON_CLASS}');
                buttons.forEach(button => {{
                    button.removeAttribute('disabled');
                    button.classList.remove('{config.BONUS_BUTTON_CLASS}_state_disabled');
                }});
            """)
            logger.info("Атрибуты disabled удалены")
        except Exception as e:
            logger.warning(f"Не удалось удалить атрибуты disabled: {e}")
        
        # Поиск и нажатие кнопки
        try:
            button = WebDriverWait(driver, config.BUTTON_TIMEOUT).until(
                EC.element_to_be_clickable(BONUS_BUTTON_SELECTOR)
            )
            
            # Двойное действие для надежности
            driver.execute_script("arguments[0].scrollIntoView();", button)
            driver.execute_script("arguments[0].click();", button)
            logger.info("Кнопка нажата через JavaScript")
            
            # Проверка успешности
            time.sleep(config.DELAY_AFTER_CLICK)
            logger.info("Действие завершено успешно")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка при нажатии кнопки: {e}")
            driver.save_screenshot(f"button_error_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
            return False

    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
        driver.save_screenshot(f"critical_error_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
        return False
    finally:
        try:
            driver.quit()
            logger.info("Браузер закрыт")
        except:
            pass

def main():
    """Основная функция с обработкой прерывания."""
    logger.info("Скрипт запущен. Для остановки нажмите Ctrl+C")
    
    attempt_count = 0
    success_count = 0
    
    try:
        while config.MAX_ATTEMPTS is None or attempt_count < config.MAX_ATTEMPTS:
            attempt_count += 1
            logger.info(f"Попытка #{attempt_count}")
            
            if click_bonus_button():
                success_count += 1
                logger.info(f"Успешных попыток: {success_count}/{attempt_count}")
            else:
                logger.warning(f"Попытка #{attempt_count} не удалась")
            
            # Проверяем, не достигли ли максимального количества попыток
            if config.MAX_ATTEMPTS is not None and attempt_count >= config.MAX_ATTEMPTS:
                logger.info(f"Достигнуто максимальное количество попыток: {config.MAX_ATTEMPTS}")
                break
            
            # Задержка до следующей попытки
            delay_hours = config.BASE_DELAY_HOURS
            delay_minutes = config.BUFFER_MINUTES + (attempt_count % 10)  # Добавляем вариативность
            total_delay = delay_hours * 3600 + delay_minutes * 60
            
            logger.info(f"Следующая попытка через {delay_hours}ч {delay_minutes}мин")
            
            # Разбиваем задержку на части для возможности прерывания
            for i in range(total_delay // 60):
                time.sleep(60)  # Спим по минуте для возможности прерывания
                
    except KeyboardInterrupt:
        logger.info("Скрипт остановлен пользователем")
    except Exception as e:
        logger.error(f"Неожиданная ошибка в основном цикле: {e}")
    finally:
        logger.info(f"Итог: {success_count} успешных попыток из {attempt_count}")
        logger.info("Скрипт завершен")

if __name__ == "__main__":
    main()
