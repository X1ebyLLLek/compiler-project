; =============================================================================
; runtime.asm — минимальная runtime-библиотека MiniCompiler (Sprint 5)
; =============================================================================
; Цель:     x86-64 Linux (ELF64)
; Синтаксис: NASM
; Соглашение: System V AMD64 ABI
;
; Экспортируемые функции:
;   _start        — точка входа процесса (вызывает main, затем exit)
;   exit          — завершить процесс (rdi = код возврата)
;   print_int     — вывести целое число в stdout (rdi = значение)
;   print_string  — вывести строку в stdout (rdi = указатель)
;   read_int      — прочитать целое из stdin → rax
;
; Сборка и линковка:
;   nasm -f elf64 -o runtime.o src/runtime/runtime.asm
;   nasm -f elf64 -o program.o program.asm
;   ld -o program runtime.o program.o
; =============================================================================

section .text

global _start
global exit
global print_int
global print_string
global read_int

; -----------------------------------------------------------------------------
; _start — точка входа процесса
;
; Вызывает main() и передаёт возвращённое значение в exit().
; Параметры командной строки не поддерживаются в этой версии.
; -----------------------------------------------------------------------------
_start:
    call main                   ; вызвать функцию main()
    mov rdi, rax                ; код возврата = возвращаемое значение main
    call exit                   ; завершить процесс

; -----------------------------------------------------------------------------
; exit(int code)
;
; Завершает процесс с указанным кодом возврата.
; Аргументы: rdi = код возврата (0..255)
; Не возвращается.
; -----------------------------------------------------------------------------
exit:
    mov rax, 60                 ; syscall: sys_exit
    syscall
    ; сюда никогда не попадём

; -----------------------------------------------------------------------------
; print_int(int64_t n)
;
; Выводит знаковое 64-битное целое число в stdout, за которым следует '\n'.
; Аргументы: rdi = число
; Сохраняет: rbp, rsp (ABI-совместим)
; -----------------------------------------------------------------------------
print_int:
    push rbp
    mov rbp, rsp
    sub rsp, 32                 ; буфер: 20 цифр + знак + '\n' + выравнивание

    mov r11, rdi                ; r11 = число (r11 caller-saved, но мы сохранили rsp/rbp)

    ; Обрабатываем знак отрицательного числа
    xor r10, r10                ; r10 = 0 (положительное)
    test r11, r11
    jns .pi_positive
    neg r11                     ; делаем положительным
    mov r10, 1                  ; отметить: исходное число отрицательное
.pi_positive:

    ; Конвертируем число в строку (цифры с конца буфера)
    ; Буфер: [rbp-32] .. [rbp-1], записываем с позиции [rbp-2] (позиция -1 = '\n')
    mov byte [rbp-1], 10        ; '\n' в конце
    lea r8, [rbp-2]             ; r8 = текущая позиция в буфере (пишем назад)
    mov r9, 10                  ; делитель

.pi_loop:
    mov rax, r11
    xor rdx, rdx
    div r9                      ; rax = rax/10, rdx = rax%10
    mov r11, rax                ; остаток в r11 для следующей итерации
    add dl, '0'
    mov byte [r8], dl
    dec r8
    test rax, rax
    jnz .pi_loop

    ; Добавляем знак минуса, если число было отрицательным
    test r10, r10
    jz .pi_write
    mov byte [r8], '-'
    dec r8

.pi_write:
    inc r8                      ; r8 = начало строки (первый символ)
    lea rdx, [rbp-1]
    sub rdx, r8
    inc rdx                     ; rdx = длина строки (включая '\n')

    mov rax, 1                  ; syscall: sys_write
    mov rdi, 1                  ; fd: stdout
    mov rsi, r8                 ; указатель на строку
    ; rdx уже содержит длину
    syscall

    mov rsp, rbp
    pop rbp
    ret

; -----------------------------------------------------------------------------
; print_string(const char* s)
;
; Выводит null-terminated строку в stdout.
; Аргументы: rdi = указатель на строку
; -----------------------------------------------------------------------------
print_string:
    push rbp
    mov rbp, rsp

    mov rsi, rdi                ; rsi = указатель на строку

    ; Вычислить длину строки (аналог strlen)
    xor rcx, rcx
.ps_len:
    cmp byte [rsi + rcx], 0
    je .ps_write
    inc rcx
    jmp .ps_len

.ps_write:
    mov rdx, rcx                ; rdx = длина
    mov rax, 1                  ; syscall: sys_write
    mov rdi, 1                  ; fd: stdout
    ; rsi = указатель (уже установлен)
    syscall

    mov rsp, rbp
    pop rbp
    ret

; -----------------------------------------------------------------------------
; read_int() -> int64_t
;
; Читает одно целое число из stdin (до пробела/переноса строки).
; Возвращает: rax = считанное число (знаковое)
; -----------------------------------------------------------------------------
read_int:
    push rbp
    mov rbp, rsp
    sub rsp, 32                 ; буфер ввода: 24 символа + выравнивание

    ; Читаем строку из stdin
    mov rax, 0                  ; syscall: sys_read
    mov rdi, 0                  ; fd: stdin
    lea rsi, [rbp-32]
    mov rdx, 23                 ; максимум 23 символа (+ место для 0)
    syscall
    ; rax = количество прочитанных байт

    ; Преобразуем строку в целое (atoi-упрощённый)
    lea rsi, [rbp-32]           ; rsi = начало буфера
    xor rax, rax                ; rax = результат
    xor r9, r9                  ; r9 = флаг знака (0 = положительный)

    ; Проверяем знак
    cmp byte [rsi], '-'
    jne .ri_digits
    mov r9, 1                   ; отрицательное число
    inc rsi

.ri_digits:
    movzx rcx, byte [rsi]
    cmp rcx, '0'
    jl .ri_done
    cmp rcx, '9'
    jg .ri_done
    sub rcx, '0'
    imul rax, rax, 10
    add rax, rcx
    inc rsi
    jmp .ri_digits

.ri_done:
    ; Применяем знак
    test r9, r9
    jz .ri_return
    neg rax

.ri_return:
    mov rsp, rbp
    pop rbp
    ret
