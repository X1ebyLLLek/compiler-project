/*
 * Симуляция заголовков стандартной библиотеки C для MiniCompiler (Sprint 7).
 *
 * Этот файл описывает сигнатуры внешних функций в синтаксисе MiniCompiler.
 * Используется для документирования и как справочник при написании extern-объявлений.
 *
 * В MiniCompiler внешние функции объявляются так:
 *   extern fn printf(int, ...) -> int;
 *   extern fn malloc(int) -> int;
 *
 * Примечание: тип указателя в MiniCompiler представляется как int (адрес),
 * так как язык пока не имеет полноценной системы указателей.
 */

/* ── Стандартный ввод-вывод (stdio.h) ─────────────────────────────── */

/*
 * printf(format, ...) -> int
 * Форматированный вывод в stdout.
 * Variadic — перед вызовом нужен xor eax, eax (количество xmm аргументов).
 *
 * extern fn printf(int) -> int;
 */

/*
 * scanf(format, ...) -> int
 * Форматированный ввод из stdin.
 * Variadic.
 *
 * extern fn scanf(int) -> int;
 */

/*
 * puts(s) -> int
 * Вывести строку + '\n' в stdout.
 *
 * extern fn puts(int) -> int;
 */

/*
 * getchar() -> int
 * Прочитать один символ из stdin.
 *
 * extern fn getchar() -> int;
 */

/*
 * putchar(c) -> int
 * Вывести один символ в stdout.
 *
 * extern fn putchar(int) -> int;
 */

/* ── Управление памятью (stdlib.h) ─────────────────────────────────── */

/*
 * malloc(size) -> int (указатель)
 * Выделить size байт. Возвращает адрес блока (0 если неудача).
 *
 * extern fn malloc(int) -> int;
 */

/*
 * free(ptr)
 * Освободить блок, выделенный malloc.
 *
 * extern fn free(int);
 */

/*
 * calloc(nmemb, size) -> int (указатель)
 * Выделить nmemb * size байт, обнулённых.
 *
 * extern fn calloc(int, int) -> int;
 */

/*
 * realloc(ptr, size) -> int (указатель)
 * Изменить размер блока.
 *
 * extern fn realloc(int, int) -> int;
 */

/* ── Операции со строками (string.h) ───────────────────────────────── */

/*
 * strlen(s) -> int
 * Длина строки (без нулевого байта).
 *
 * extern fn strlen(int) -> int;
 */

/*
 * strcpy(dst, src) -> int (указатель)
 * Скопировать строку src в dst.
 *
 * extern fn strcpy(int, int) -> int;
 */

/*
 * strcmp(s1, s2) -> int
 * Сравнить строки. 0 если равны, <0 или >0 иначе.
 *
 * extern fn strcmp(int, int) -> int;
 */

/*
 * memcpy(dst, src, n) -> int (указатель)
 * Скопировать n байт из src в dst.
 *
 * extern fn memcpy(int, int, int) -> int;
 */

/*
 * memset(dst, c, n) -> int (указатель)
 * Заполнить n байт значением c.
 *
 * extern fn memset(int, int, int) -> int;
 */

/* ── Математические функции (math.h) ───────────────────────────────── */

/*
 * exit(code)
 * Завершить процесс с кодом code.
 *
 * extern fn exit(int);
 */

/*
 * atoi(s) -> int
 * Преобразовать строку в целое число.
 *
 * extern fn atoi(int) -> int;
 */

/*
 * rand() -> int
 * Псевдослучайное число [0, RAND_MAX].
 *
 * extern fn rand() -> int;
 */

/*
 * srand(seed)
 * Установить начальное значение для rand().
 *
 * extern fn srand(int);
 */
