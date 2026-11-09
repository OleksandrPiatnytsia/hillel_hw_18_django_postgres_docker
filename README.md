# hillel_hw_18 — Django: книгарня в Docker (PostgreSQL, Redis)

Навчальний Django-проєкт (Hillel). Продовження ДЗ №16 (автентифікація, права
доступу, логування). У цьому ДЗ:

- **docker-compose**: сервіси `web` (Django + gunicorn), `db` (PostgreSQL 17), `redis` (Redis 8);
- **volumes** для бази, статики й обкладинок; **healthchecks** для всіх трьох сервісів;
- **`docker-entrypoint.sh`**: міграції й `collectstatic` автоматично при кожному старті;
- **перенесення даних** з SQLite у PostgreSQL (`dumpdata` / `loaddata` з природними ключами);
- **налаштування з `.env`**: PostgreSQL, Redis (кеш і сесії), WhiteNoise для статики;
- `/health/`: перевірка PostgreSQL і Redis (200 / 503).

## Стек

- Python 3.13, Django 6.1
- PostgreSQL 17 (`psycopg` 3), Redis 8 (вбудований у Django `RedisCache`)
- Docker, docker compose; gunicorn; WhiteNoise (статика без nginx)
- Bootstrap 5.3 (через CDN, із перевіркою `integrity`)
- Pillow: перевірка зображень для `ImageField`
- python-dotenv: налаштування з `.env`
- django-debug-toolbar 8.0 (тільки для розробки, `requirements-dev.txt`)

## Сторінки сайту

| URL | Ім'я маршруту | View | Доступ | Що робить |
|---|---|---|---|---|
| `/` | `books:list` | `BookListView` | усі | каталог: фільтри, сортування, пагінація по 10 книг |
| `/<pk>/` | `books:detail` | `BookDetailView` | усі | сторінка книги |
| `/create/` | `books:create` | `BookCreateView` | `books.add_book` | додавання книги |
| `/<pk>/update/` | `books:update` | `BookUpdateView` | `books.change_book` | редагування книги |
| `/<pk>/delete/` | `books:delete` | `BookDeleteView` | `books.delete_book` | підтвердження й видалення |
| `/authors/` | `books:author_list` | `AuthorListView` | усі | автори з кількістю книг |
| `/authors/<pk>/` | `books:author_detail` | `AuthorDetailView` | усі | автор, біографія та його книги |
| `/accounts/login/` | `users:login` | `UserLoginView` | усі | вхід (за username) |
| `/accounts/logout/` | `users:logout` | `UserLogoutView` | POST | вихід |
| `/accounts/signup/` | `users:signup` | `SignUpView` | гості | реєстрація |
| `/accounts/profile/` | `users:profile` | `ProfileView` | залогінені | групи й права поточного користувача |
| `/admin/` | `admin:index` | | `is_staff` | адмінка |
| `/health/` | `health` | `health` (`config/views.py`) | усі, GET | стан PostgreSQL і Redis: 200 або 503, JSON |
| `/__debug__/` | | | `DEBUG` + `INTERNAL_IPS` | службові адреси Debug Toolbar |

Маршрути описані в `books/urls.py` (`app_name = "books"`) і `users/urls.py`
(`app_name = "users"`) і підключені в `config/urls.py` через `include()`. У шаблонах і коді адреси
будуються тільки за іменами: `{% url 'books:detail' book.pk %}`,
`reverse_lazy("books:list")`.

## Структура

```
config/
├── settings.py              # PostgreSQL, Redis, WhiteNoise, AUTH_USER_MODEL, Debug Toolbar, LOGGING
├── urls.py                  # admin + books + accounts/ + health/ + media і __debug__ у DEBUG
├── views.py                 # health: перевірка PostgreSQL і Redis
├── middleware.py            # RequestTimingMiddleware
└── logging_filters.py       # HideClientErrorTraceback (403/404 без traceback)
users/
├── models.py                # User(AbstractUser): email обов'язковий, унікальний, lowercase
├── forms.py                 # LoginForm, SignUpForm (+ Bootstrap-класи)
├── views.py                 # UserLoginView, UserLogoutView, SignUpView, ProfileView
├── urls.py                  # app_name = "users"
├── admin.py                 # UserAdmin з email на сторінці «Add user»
├── signals.py               # логування входу, виходу й невдалих спроб
├── apps.py                  # підключення сигналів у ready()
├── migrations/
│   ├── 0001_initial.py
│   ├── 0002_lowercase_email.py    # дані → lowercase + CheckConstraint
│   └── 0003_create_groups.py      # групи Customers / Editors / Managers
└── templates/users/
    ├── auth_form.html       # спільний для входу й реєстрації
    └── profile.html
books/
├── models.py                # Category, Author, Book (+ cover), BookCategory, BookQuerySet
├── forms.py                 # BookForm, BookFilterForm, CoverInput
├── views.py                 # Class-Based Views для книг і авторів
├── urls.py                  # app_name = "books"
├── admin.py                 # адмінка (+ мініатюри обкладинок)
├── templates/books/
│   ├── book_list.html
│   ├── book_detail.html
│   ├── book_form.html             # спільний для Create і Update
│   ├── book_confirm_delete.html
│   ├── author_list.html
│   ├── author_detail.html
│   ├── includes/stock_badge.html  # бейдж наявності
│   └── widgets/cover_input.html   # поле обкладинки з прев'ю
└── management/commands/
    ├── seed_books.py
    └── book_stats.py
templates/                   # спільні шаблони проєкту
├── base.html
├── 403.html                 # «Access denied»
└── includes/
    ├── navbar.html
    ├── messages.html
    └── pagination.html
static/                      # статика проєкту
├── css/styles.css
└── img/
    ├── no-cover.svg         # заглушка, коли обкладинки немає
    └── favicon.svg
media/                       # завантажені обкладинки (не в git)
logs/                        # app.log і його ротації (не в git)
requirements.txt             # залежності проєкту
requirements-dev.txt         # + django-debug-toolbar
Dockerfile                   # образ web: python:3.13-slim, користувач app, gunicorn
.dockerignore                # що не потрапляє в образ (.env, .venv, бази, media)
docker-entrypoint.sh         # migrate + collectstatic, потім exec команди
docker-compose.yml           # web + db + redis, volumes, healthchecks
.gitattributes               # *.sh завжди з LF
```

## Користувачі та автентифікація

### Custom User Model

`users.User` наслідується від `AbstractUser`: усе вбудоване (username,
пароль, імена, `is_staff`, групи, права) лишається, змінено тільки email.

```python
# config/settings.py
AUTH_USER_MODEL = "users.User"
```

`AUTH_USER_MODEL` треба задати **до першого** `migrate`: таблиці адмінки, груп
і прав отримують зовнішній ключ саме на цю модель. Тому проєкт стартував з
нової бази (дані книжок перенесено через `dumpdata` / `loaddata`).

**Email:**
- обов'язковий і унікальний (`unique=True`, текст помилки в `error_messages`);
- завжди в нижньому регістрі: `User.clean()` (форми, адмінка) і `User.save()`
  (`createsuperuser`, `create_user()`, скрипти) переводять його в lowercase,
  тому `Ann@Mail.com` і `ann@mail.com` вважаються однією адресою;
- `CheckConstraint` `users_user_email_lowercase` гарантує це на рівні бази,
  навіть для `QuerySet.update()` і сирого SQL;
- міграція `0002_lowercase_email` спершу переводить наявні email у lowercase,
  а вже потім додає обмеження.

Вхід за **username** (як у вбудованого користувача).

### Вхід, вихід, реєстрація

| Сторінка | Як зроблено |
|---|---|
| Вхід | `LoginView` + `AuthenticationForm`; `redirect_authenticated_user = True`; повертає на `?next=...` |
| Вихід | `LogoutView`, **тільки POST** (Django 5+): у меню це кнопка всередині `<form>` з CSRF-токеном, а не посилання |
| Реєстрація | `CreateView` + `SignUpForm(UserCreationForm)`; після збереження `login()`, новий користувач потрапляє в групу Customers |

```python
LOGIN_URL = "users:login"            # куди Login/PermissionRequiredMixin відправляють гостей
LOGIN_REDIRECT_URL = "books:list"    # після входу, якщо немає ?next=
LOGOUT_REDIRECT_URL = "books:list"
```

`SignUpView` теж поважає `?next=`, але перевіряє адресу через
`url_has_allowed_host_and_scheme`, щоб не було переадресації на чужий сайт
(open redirect). Перевірку паролів (`AUTH_PASSWORD_VALIDATORS`), хешування і
перевірку username без урахування регістру робить сама `UserCreationForm`.

## Права доступу та групи

### Групи

Створюються data migration `users/0003_create_groups.py`:

| Група | Права (застосунок `books`) | Що може |
|---|---|---|
| **Customers** | `view_book`, `view_author`, `view_category` | лише переглядати; дається кожному новому користувачу |
| **Editors** | Customers + `add/change_book`, `add/change_author`, права на `bookcategory` | додавати й редагувати книжки й авторів |
| **Managers** | Editors + `delete_book`, `delete_author`, `add/change/delete_category`, `manage_stock` | усе, зокрема видаляти й змінювати склад |

Суперкористувач має всі права без груп. Додати користувача в групу:
адмінка → Users → користувач → Groups.

Permissions зазвичай створює сигнал `post_migrate`, тобто **після** всіх
міграцій. На новій базі їх ще немає в момент `0003`, тому міграція спершу
викликає `create_permissions()` сама. Якщо в назві права помилка, міграція
падає з `RuntimeError`. Відкат (`migrate users 0002`) видаляє групи.

### Перевірка прав

- **Views:** `PermissionRequiredMixin` стоїть першим у списку батьківських класів:
  ```python
  class BookCreateView(PermissionRequiredMixin, BookFormUserMixin, SuccessMessageMixin, CreateView):
      permission_required = "books.add_book"
  ```
  Гість отримує переадресацію на `LOGIN_URL?next=...`, а залогінений
  користувач без права отримує 403 (`templates/403.html`). Тому окремий
  `LoginRequiredMixin` тут не потрібен.
- **`LoginRequiredMixin`** стоїть на `ProfileView`: сторінка не вимагає
  конкретного права, достатньо бути залогіненим.
- **Шаблони:** `{% if perms.books.change_book %}` ховає кнопки Edit / Delete /
  Add book. Це лише зручність, справжній захист у views.

### Власний permission `manage_stock`

```python
class Book(models.Model):
    class Meta:
        permissions = [("manage_stock", "Can change stock quantity")]
```

`BookForm.__init__(user=...)` робить поле `stock` неактивним (`disabled`),
якщо в користувача немає `books.manage_stock`. Для такого поля Django
**ігнорує** значення з POST і бере початкове, тож змінити склад через
DevTools не вийде. Редактор створює книжку з `stock = 0`, а склад виставляє менеджер.

### Профіль

`/accounts/profile/` показує групи, статус (superuser / staff), коротке
«що я можу» (✅/❌) і повний список `user.get_all_permissions()`.

## Django Debug Toolbar

Лише для розробки. Вмикається, коли виконуються всі три умови:

```python
ENABLE_DEBUG_TOOLBAR = (
    DEBUG and find_spec("debug_toolbar") is not None and "test" not in sys.argv
)
```

- `DEBUG=True`: у продакшні тулбара немає взагалі (ні в `INSTALLED_APPS`, ні в URL);
- пакет встановлено (`requirements-dev.txt`): з одним `requirements.txt` проєкт працює;
- не `manage.py test`.

Тулбар бачать лише запити з `INTERNAL_IPS = ["127.0.0.1", "::1"]`, незалежно
від того, хто залогінений. Так можна дивитися SQL і шаблони очима гостя чи
звичайного покупця. `DebugToolbarMiddleware` стоїть одразу після `SecurityMiddleware`.

Тулбар зберігає дані в пам'яті (`MemoryStore`), тому його міграція прихована
і `migrate` її не показує, це нормально.

**У Docker тулбара немає:** образ ставить лише `requirements.txt`, і
`find_spec("debug_toolbar")` повертає `None`. Це навмисно: запити з Mac
приходять у контейнер з адреси шлюзу Docker (`192.168.65.1`), а не з
`127.0.0.1`, тож для тулбара довелося б розширювати `INTERNAL_IPS`. Для
налагодження з тулбаром запускайте `runserver` локально (див. «Встановлення та запуск»).

## Логування

`LOGGING` у `config/settings.py`: вивід у консоль і у файл `logs/app.log`
(`RotatingFileHandler`: 1 МБ, 5 архівних файлів, `utf-8`). Формат:

```
2026-11-07 21:02:39,943 INFO users.signals Login: user=ann ip=127.0.0.1
```

| Логер | Рівень | Що пише |
|---|---|---|
| `users` | DEBUG при `DEBUG=True`, інакше INFO | вхід, вихід, невдалий вхід (WARNING), реєстрація |
| `books` | так само | створення, зміна (`form.changed_data`), видалення книжок, хто це зробив |
| `config` | INFO | рядок на кожен запит від `RequestTimingMiddleware` |
| `django` | WARNING | 404, 403 одним рядком; 500 з traceback |

- Події входу й виходу ловлять сигнали `user_logged_in`, `user_logged_out`,
  `user_login_failed` (`users/signals.py`): вони спрацьовують для будь-якого
  входу, зокрема в адмінці.
- У лог **не** пишуться паролі й email (персональні дані).
- `HideClientErrorTraceback` (`config/logging_filters.py`) прибирає traceback з
  записів про 4xx: для 403 це звичайна відмова, а не помилка. Фільтр стоїть на
  обробниках (handlers), бо фільтри логера `django` не діють на записи від
  дочірнього `django.request`.

```bash
tail -f logs/app.log             # локальний runserver
docker compose logs -f web       # у Docker: консольний вивід контейнера
```

У Docker `logs/app.log` пишеться всередині контейнера й зникає, коли контейнер
перестворюється (volume для логів немає). Основне джерело там — `docker compose logs`.
Access log gunicorn вимкнено: рядок на кожен запит уже пише `RequestTimingMiddleware`,
а `/health/` (Docker перевіряє його кожні 10 секунд) middleware не логує.

## Middleware: `RequestTimingMiddleware`

`config/middleware.py`, **перший** у `MIDDLEWARE`, тому вимірює роботу всіх
інших middleware, view і шаблону.

```
INFO config.middleware GET /?page=2&sort=price 200 23.6ms user=anonymous
INFO config.middleware GET /create/ 403 3.6ms user=ann
```

- **Лог:** метод, шлях із query string, статус, час, користувач. Запити довші
  за `REQUEST_SLOW_MS = 500` пишуться як WARNING. `/media/`, `/__debug__/` і `/health/` не логуються.
- **Заголовки:** `X-Request-Duration: 23.6ms` і стандартний
  `Server-Timing: app;dur=23.6` (видно в DevTools → Network → Timing).
- Час рахується через `time.perf_counter()` (монотонний годинник).
- `request.user` доступний, хоча middleware стоїть вище за
  `AuthenticationMiddleware`: та присвоює його тому самому об'єкту `request`
  ще до того, як відповідь повертається до нас.

Реєстрація й вхід займають ~300 мс, решта сторінок кілька мілісекунд: це
хешування пароля (PBKDF2), воно навмисно повільне.

## Class-Based Views

| View | Шаблон за замовчуванням | Особливості |
|---|---|---|
| `BookListView` | `books/book_list.html` | `paginate_by = 10`; фільтри з GET-параметрів через `BookFilterForm`; `prefetch_related("categories")` |
| `BookDetailView` | `books/book_detail.html` | `prefetch_related("categories")` |
| `BookCreateView` | `books/book_form.html` | `PermissionRequiredMixin` (`add_book`); після збереження редирект на `get_absolute_url()` |
| `BookUpdateView` | `books/book_form.html` | `PermissionRequiredMixin` (`change_book`); той самий шаблон; заголовок і кнопки залежать від `object` |
| `BookDeleteView` | `books/book_confirm_delete.html` | `PermissionRequiredMixin` (`delete_book`); видалення тільки через POST; редирект на каталог |
| `AuthorListView` | `books/author_list.html` | `annotate(Count("books"))`, `paginate_by = 20` |
| `AuthorDetailView` | `books/author_detail.html` | книги автора через `author.books` |

Сторінки авторів тільки для перегляду: авторів додають і редагують в адмінці.
Посилання в адмінку видно, якщо користувач має `is_staff` **і** право
`add_author` / `change_author`.

Після створення, редагування й видалення `SuccessMessageMixin` показує
повідомлення (messages framework → Bootstrap alert), а `form_valid()`
пише запис у лог (див. «Логування»).

## Шаблони

- `base.html`: каркас сторінки з блоками `title` і `content`. Сторінки
  наслідуються від нього через `{% extends "base.html" %}`.
- `navbar.html`: прилипає до верху під час прокручування (`sticky-top`),
  підсвічує активний пункт меню (`request.resolver_match.url_name`), має
  швидкий пошук і на вузькому екрані згортається в «бургер». Праворуч:
  «Log in» / «Sign up» для гостей або меню користувача (email, «My profile»,
  «Log out»). «Add book» видно лише з правом `add_book`, «Admin» лише при `is_staff`.
- `pagination.html`: універсальна пагінація для будь-якого `ListView`.
  Тег `{% querystring page=N %}` зберігає поточні фільтри при переході між
  сторінками; довгий список сторінок скорочується (`get_elided_page_range`).
- `messages.html`: flash-повідомлення.

### Фільтри каталогу

Форма `BookFilterForm`, метод GET (фільтри видно в адресі, сторінку можна
зберегти в закладки):

| Параметр | Що робить |
|---|---|
| `q` | пошук за назвою або іменем автора (без урахування регістру, зокрема для кирилиці) |
| `category` | категорія за `slug` |
| `author` | автор за `pk` |
| `stock` | наявність: `in_stock` / `low` (≤ 5) / `out` |
| `price_min`, `price_max` | діапазон ціни; якщо «від» більше за «до», форма покаже помилку |
| `sort` | `title`, `-title`, `author__name`, `price`, `-price`, `-created_at` |

Некоректні значення (`?price_min=abc`) не ламають сторінку: форма показує
помилку, а каталог виводить усі книги.

## Статичні файли і media

| | Static | Media |
|---|---|---|
| Що це | CSS, іконки, заглушка обкладинки | обкладинки, завантажені через форму |
| Де лежить | `static/` (у git) | `media/covers/<рік>/<місяць>/` (не в git) |
| Налаштування | `STATIC_URL`, `STATICFILES_DIRS`, `STATIC_ROOT` | `MEDIA_URL`, `MEDIA_ROOT` |
| Хто роздає локально | `runserver` сам | `static()` у `config/urls.py` (тільки при `DEBUG=True`) |
| Хто роздає в Docker | WhiteNoise з `STATIC_ROOT` (volume `static_data`) | `static()`, тому в Docker `DJANGO_DEBUG=True` |

- У шаблонах статика підключається через `{% load static %}` і `{% static '...' %}`.
- `collectstatic` запускає `docker-entrypoint.sh` при кожному старті контейнера.
  `CompressedStaticFilesStorage` (WhiteNoise) додатково створює стиснені `.gz` і `.br` копії.
  Не `CompressedManifestStaticFilesStorage`: при `DEBUG=False` (а `manage.py test`
  завжди працює з ним) він вимагає вже зібраний manifest, і тести з `{% static %}` падали б.
- WhiteNoise роздає лише статику, яка була на диску при старті, а не завантажені
  файли. Тому обкладинки в Docker роздає Django при `DEBUG=True`. Правильне
  рішення для продакшну — nginx (окрема задача).

### Обкладинки книг

- Поле `Book.cover` (`ImageField`, необов'язкове).
- `Book.cover_url` повертає адресу обкладинки, а якщо її немає, то заглушки.
- Перевірки під час завантаження:
  - файл справді є зображенням (Pillow);
  - формат JPG, PNG або WebP (SVG і GIF заборонені);
  - розмір до 2 МБ.
- На сторінці редагування видно прев'ю поточної обкладинки й чекбокс
  «Remove cover» (власний віджет `CoverInput` на основі `ClearableFileInput`).
- Форма відправляється з `enctype="multipart/form-data"`, без нього файл не дійшов би на сервер.

## Моделі

| Модель | Поля | Примітки |
|---|---|---|
| `Category` | `name`, `slug` | обидва унікальні |
| `Author` | `name`, `bio` | `name` унікальне; `bio` необов'язкове |
| `Book` | `title`, `author`, `price`, `description`, `stock`, `cover`, `categories`, `created_at`, `updated_at` | `price ≥ 0`; `author` — ForeignKey на `Author` з `on_delete=PROTECT` (не можна видалити автора, у якого є книги); зв'язок ManyToMany з категоріями через `BookCategory`; `get_absolute_url()`, `cover_url`, `is_low_stock` |
| `BookCategory` | `book`, `category` | проміжна модель; `on_delete=PROTECT` не дає видалити категорію, у якій є книги; пара `book + category` унікальна |

`BookQuerySet.by_stock_status()` фільтрує книги за наявністю. Його
використовують і каталог, і адмінка; поріг «мало» задає `LOW_STOCK_THRESHOLD = 5`.

### Перенесення авторів в окрему модель

Раніше автор був текстовим полем `Book.author`. Перенесення зроблено
чотирма міграціями, щоб не втратити дані:

| Міграція | Що робить |
|---|---|
| `0003_rename_author_book_author_name` | перейменовує текстове поле на `author_name` |
| `0004_author_book_author` | створює `Author` і тимчасовий необов'язковий `Book.author` |
| `0005_move_authors_to_author_model` | data migration: для кожного імені створює `Author` (`get_or_create`) і пов'язує з книгами |
| `0006_remove_book_author_name_alter_book_author` | видаляє `author_name`, робить `author` обов'язковим |

Просто замінити `CharField` на `ForeignKey` під тим самим іменем не можна:
Django згенерував би `AlterField` і спробував би перетворити імена авторів на числові id.
Усі чотири міграції можна відкотити (`python manage.py migrate books 0002`).

## Адмінка

- **Книги:**
  - колонки: мініатюра обкладинки, автор, категорії, ознака наявності;
  - автор вибирається з пошуком під час введення (`autocomplete_fields`);
  - ціну й кількість можна редагувати прямо у списку;
  - фільтри: наявність (є / мало ≤ 5 / немає), категорії, дата;
  - пошук за назвою, іменем автора, описом і категорією;
  - `date_hierarchy`, `fieldsets` із секцією «Cover» (прев'ю обкладинки), inline для категорій.
- **Автори:** кількість книг (із сортуванням), пошук за іменем, біографія.
- **Категорії:** кількість книг (із сортуванням), автозаповнення `slug`,
  inline зі списком книг.
- Запити оптимізовано через `select_related` / `prefetch_related` та `annotate`.

## Встановлення та запуск

### У Docker

```bash
cp .env.example .env
# згенерувати SECRET_KEY і вставити в .env В ОДИНАРНИХ ЛАПКАХ (див. нижче):
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
# заповнити POSTGRES_PASSWORD

docker compose up --build -d                                   # зібрати образ і запустити
docker compose ps                                              # усі три сервіси (healthy)
docker compose exec web python manage.py createsuperuser
docker compose exec web python manage.py seed_books            # або перенести дані, див. нижче
```

- Сайт: http://localhost:8000/
- Адмінка: http://localhost:8000/admin/
- Стан: http://localhost:8000/health/
- Лог: `docker compose logs -f web`

```
docker compose up
  ├─ db     postgres:17-alpine  ──┐ healthcheck: pg_isready
  ├─ redis  redis:8-alpine      ──┤ healthcheck: redis-cli ping
  │                               ▼ обидва healthy (depends_on: condition: service_healthy)
  └─ web    Dockerfile → docker-entrypoint.sh → migrate → collectstatic → exec gunicorn
                                    healthcheck: GET /health/
```

| Сервіс | Порт на Mac | Volume | Healthcheck |
|---|---|---|---|
| `db` | 5432 | `postgres_data` → `/var/lib/postgresql/data` | `pg_isready` |
| `redis` | 6379 | немає (кеш можна втратити, сесії є і в PostgreSQL) | `redis-cli ping` |
| `web` | 8000 | `static_data` → `/app/staticfiles`, `media_data` → `/app/media` | `GET /health/` (Python `urllib`, у slim-образі немає curl) |

Корисні команди:

```bash
docker compose logs -f web                         # вивід Django / gunicorn
docker compose exec web python manage.py shell     # команда в запущеному контейнері
docker compose restart web                         # перезапуск (entrypoint знову зробить migrate)
docker compose down                                # зупинити й видалити контейнери, volumes лишаються
docker compose down -v                             # ... і ВИДАЛИТИ volumes: базу й обкладинки!
```

**Що варто знати:**

- `docker-entrypoint.sh` має `set -e`: якщо `migrate` впаде, gunicorn не стартує.
  `exec "$@"` робить gunicorn процесом PID 1, тому він отримує `SIGTERM` від
  `docker compose stop` і завершується коректно.
- Контейнер працює від користувача `app` (не root). Писати він може лише в
  `staticfiles/`, `media/`, `logs/`. Файли, скопійовані через `docker compose cp`,
  належать root: `docker compose exec -u root web chown -R app:app /app/media`.
- `.env` не потрапляє в образ (`.dockerignore`), compose передає змінні через
  `env_file`. Хости в `.env` — `localhost` (для локального запуску);
  `docker-compose.yml` перевизначає їх для `web`: `POSTGRES_HOST=db`,
  `REDIS_URL=redis://redis:6379/0` (сервіси бачать один одного за іменем).
- **`$` у значеннях `.env`.** Docker compose сприймає `$abc` як змінну й підставляє
  порожній рядок (`WARN The "abc" variable is not set`). Ключ від
  `get_random_secret_key()` може містити `$`, тому його беремо в **одинарні**
  лапки: `DJANGO_SECRET_KEY='...'`. Подвійні лапки не допомагають.
- gunicorn запускається з `--no-control-socket`: з версії 25.1 він відкриває сокет
  для `gunicornc` у `$HOME`, а в користувача `app` немає домашньої папки.

### Локально (runserver + PostgreSQL і Redis з Docker)

Для розробки з Debug Toolbar. PostgreSQL і Redis беруться з контейнерів через
опубліковані порти (`POSTGRES_HOST=localhost`, `REDIS_URL=redis://localhost:6379/0` у `.env`).

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt   # або requirements.txt без Debug Toolbar

docker compose up -d db redis         # тільки база й Redis
python manage.py migrate
python manage.py runserver
```

- Сайт: http://127.0.0.1:8000/ (саме `127.0.0.1`, щоб з'явився Debug Toolbar)
- Лог: `logs/app.log`
- Якщо контейнер `web` теж запущений, він уже займає порт 8000:
  `docker compose stop web` або `runserver 8001`.

### Перенесення даних із SQLite у PostgreSQL

Так дані з ДЗ №16 (`db.sqlite3`, `media/`) переїхали в Docker:

```bash
# 1. Поки settings.py ще на SQLite (до перемикання на PostgreSQL):
DJANGO_DEBUG=False python manage.py dumpdata --natural-foreign --natural-primary --exclude contenttypes --exclude auth.permission --exclude admin.logentry --exclude sessions --indent 2 -o data.json

# 2. У запущений контейнер web (migrate вже створив таблиці й групи):
docker compose cp data.json web:/tmp/data.json
docker compose exec web python manage.py loaddata /tmp/data.json
docker compose exec -u root web rm /tmp/data.json

# 3. Обкладинки у volume media_data:
docker compose cp media/. web:/app/media/
docker compose exec -u root web chown -R app:app /app/media
```

- `DJANGO_DEBUG=False`: щоб у дамп не потрапив `debug_toolbar` (змінна з
  командного рядка важливіша за `.env`, `load_dotenv()` її не перезаписує).
- `--natural-foreign`: зв'язки за природними ключами, а не за `id`: група як
  `["Editors"]`, permission як `["manage_stock", "books", "book"]`. `id` permissions
  у PostgreSQL інші, тому інакше не можна.
- `--natural-primary`: у `User` і `Group` немає `pk`. Групи вже створила
  міграція `users.0003`, `loaddata` знаходить їх за назвою й оновлює, а не дублює.
- `contenttypes`, `auth.permission` створює `migrate`; лог адмінки й сесії не переносимо.
- Книги, автори, категорії переносяться зі своїми `id` (адреси `/15/` не змінюються).
  `loaddata` на PostgreSQL сам скидає sequences: нова книга отримує наступний `id`.
- `data.json` містить хеші паролів і email, тому він у `.gitignore` і `.dockerignore`.
- Перевірка: кількість записів кожної моделі збігається з дампом
  (`bookcategory 18`, `book 12`, `author 10`, `category 5`, `group 3`, `user 3`).

### Змінні оточення (`.env`)

| Змінна | Опис | Приклад |
|---|---|---|
| `DJANGO_SECRET_KEY` | секретний ключ (обов'язковий), в одинарних лапках | `'change-me'` |
| `DJANGO_DEBUG` | режим налагодження; при `False` media не роздаються (і в Docker теж) | `True` |
| `DJANGO_ALLOWED_HOSTS` | хости через кому (`localhost` потрібен і для healthcheck) | `127.0.0.1,localhost` |
| `POSTGRES_DB` | назва бази (обов'язкова); контейнер `db` створює її при першому старті | `bookstore` |
| `POSTGRES_USER` | користувач бази (обов'язковий) | `bookstore` |
| `POSTGRES_PASSWORD` | пароль (обов'язковий) | |
| `POSTGRES_HOST` | `localhost` для runserver; у Docker compose ставить `db` | `localhost` |
| `POSTGRES_PORT` | порт | `5432` |
| `REDIS_URL` | Redis для кешу й сесій; у Docker compose ставить `redis://redis:6379/0` | `redis://localhost:6379/0` |

`POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` читають і Django, і образ
`postgres`, тому один `.env` обслуговує обидва. Змінювати їх після першого старту
`db` марно: база вже створена у volume.

## Redis

- **Кеш** (`CACHES`, `RedisCache`): один спільний для всіх worker-процесів gunicorn
  (`LocMemCache` за замовчуванням був би окремим у кожному процесі).
- **Сесії** (`SESSION_ENGINE = cached_db`): читаються з Redis, записуються і в
  Redis, і в PostgreSQL. Після перезапуску Redis ніхто не вилогінюється.

## `/health/`

`config/views.py`: `SELECT 1` у PostgreSQL і `cache.set` / `cache.get` випадкового
значення в Redis.

```
200 {"status": "ok", "database": "ok", "cache": "ok"}
503 {"status": "error", "database": "ok", "cache": "error"}
```

- 503, а не 500: Django працює, недоступний сервіс, від якого він залежить.
- Подробиці помилки пишуться тільки в лог (`config.views`), не у відповідь.
- `@never_cache`, `@require_GET`; сесію не читає, тому працює й без Redis.
- Перевірено: `docker compose stop redis` → 503, `web` за ~30 с стає `unhealthy`;
  `docker compose start redis` → знову `healthy` без перезапуску `web`.
  Docker compose сам `unhealthy`-контейнери не перезапускає, лише показує стан.

## Management-команди

### `seed_books`

Створює 5 категорій, 10 авторів і 12 книг. Команду можна запускати повторно,
дублікати не створюються.

```bash
python manage.py seed_books
```

### `book_stats`

Виводить статистику книгарні та демонструє можливості ORM:

1. **filter**:
   - у наявності й дешевші за задану ціну;
   - мало на складі, немає на складі;
   - книги певної категорії, книги без категорії;
2. **Q-об'єкти**:
   - пошук за назвою / автором / категорією (OR);
   - «у наявності, але не в категорії» (AND + NOT);
   - складна умова для акції;
3. **annotate**:
   - статистика по категоріях;
   - топ-5 книг за вартістю запасу (`F("price") * F("stock")`);
   - категорії з понад 2 книгами (HAVING);
4. **aggregate**: підсумок по всьому магазину.

```bash
python manage.py book_stats
python manage.py book_stats --max-price 200 --search кінг --category fentezi
python manage.py book_stats --sql   # також показати згенерований SQL
```

| Параметр | За замовчуванням | Опис |
|---|---|---|
| `--max-price` | `300` | максимальна ціна для фільтра |
| `--search` | `Кінг` | рядок пошуку для Q-запиту |
| `--category` | `fentezi` | slug категорії |
| `--sql` | | друкувати SQL кожного запиту |

## Кирилиця в PostgreSQL

**Пошук.** `icontains` на PostgreSQL — це `UPPER(title) LIKE UPPER('%вбив%')`, і
`UPPER` для кирилиці працює правильно. Тому `books/sqlite_functions.py` з ДЗ №16
(власний `LIKE` для SQLite) видалено.

**Сортування.** Образ `postgres:17-alpine` за замовчуванням створює базу з
collation libc (`en_US.utf8`, провайдер `c`). Але musl (бібліотека C в Alpine)
не має правил сортування для мов, тому рядки порівнювались за кодами Unicode,
як у SQLite:

```
Є (U+0404)  І (U+0406)  Ї (U+0407)  А…Я (U+0410–042F)  а…я (U+0430–044F)  Ґ (U+0490)
ORDER BY:  Євген, Іван, Ївга, Андрій, Борис, …, Яна, андрій, Ґанна
```

Рішення — ICU (бібліотека з правилами сортування для мов, вбудована в образ):

```yaml
POSTGRES_INITDB_ARGS: "--locale-provider=icu --icu-locale=uk-UA"
```

```
ORDER BY:  андрій, Андрій, Борис, Гліб, Ґанна, Євген, Ирина, Іван, Ївга, Яна
```

- Діє на всю базу: моделі й `order_by` не змінювались.
- `initdb` виконується лише на порожньому volume. Щоб застосувати до існуючої
  бази: `docker compose down`, `docker volume rm <проєкт>_postgres_data`,
  `docker compose up -d` і знову `loaddata` (volume `media_data` не чіпаємо,
  тому **не** `down -v`).
- Перевірка: `SELECT datlocprovider FROM pg_database WHERE datname = current_database()`
  повертає `i` (ICU).

## Відомі обмеження

- **Старі файли обкладинок не видаляються.** Django не прибирає файл з
  диска, коли книгу видалено, обкладинку замінено або позначено «Remove».
  Такі файли лишаються в `media/` (у Docker — у volume `media_data`).
- **Docker працює з `DJANGO_DEBUG=True`.** Інакше Django не роздає обкладинки,
  а WhiteNoise вміє лише статику. Для продакшну потрібен nginx (окрема задача):
  він роздаватиме `/media/` і `/static/` з volumes, а Django перейде на `DEBUG=False`.
- **IP у логах — це `REMOTE_ADDR`.** У Docker це адреса шлюзу (`192.168.65.1`),
  за проксі (nginx) буде адреса проксі; справжню треба брати з `X-Forwarded-For`,
  налаштувавши довіру до проксі.
- **`logs/app.log` у контейнері не зберігається** між перестворенням контейнера
  (немає volume); у Docker логи дивимось через `docker compose logs`.
- **Вихід у лозі middleware показується як `user=anonymous`**: `logout()`
  змінює `request.user` раніше, ніж middleware його читає. Хто вийшов, видно в
  рядку `Logout: user=...` від сигналу.
- **Немає скидання пароля й підтвердження email.** Для цього потрібна
  відправка листів (`PasswordResetView`); заплановано.
- **Валюта одна.** Ціни показуються з `₴`; підтримку кількох валют
  (UAH, USD) заплановано на наступні домашки.

## Плани

- nginx перед gunicorn: роздача static і media, `DEBUG=False` у Docker;
- i18n: українська та англійська мови інтерфейсу;
- валюти: модель `Currency` (UAH, USD);
- скидання пароля й підтвердження email;
- тести для views, форм, фільтрів і прав доступу.
