# I certify that no unauthorized assistance has been received or
# given in the completion of this work
# Oliver Chen

import sys
import os

debug = False

SPECIAL = ("<", ">", "(", ")", "[", "]", "\\", ".", ",", ";", ":", "@", "\"")
SP = (" ", "\t")
ALPHA = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
DIGIT = "0123456789"

stream = []  # iterator for stdin
next_char = ""  # 1 character lookahead
state = 0  # 0 = expecting mail from , 1 = expecting rcpt to, 2 = expecting rcpt to or data, 3 = expecting data body
forward_paths = set()  # set of unique forward paths
path_buffer = ""  # temporary buffer for forward paths
get_path = False  # flag to insert to path_buffer
data = ""  # temporary buffer for data
data_buffer = ""  # temporary buffer for detecting end of data message


def main():
    global stream, next_char, state, forward_paths, path_buffer, data, data_buffer
    for line in sys.stdin:
        print(line, end="")
        global stream, next_char
        stream = iter(line)
        put_next()
        """
        Requirements:
        - [ ] Save forward-path
        - [ ] Access and write to each of forward/forward-path
        - [x] Save data body
        - [x] Write data body to intended forward paths
        """
        if state == 3:
            res = read_data()
            if res != "":
                # found proper end of message
                # TODO: remove debug
                forward_paths = ["example1@unc.edu", "example2@unc.edu", "example3@unc.edu"]
                for fpath in forward_paths:
                    with open(f"./forward/{fpath}", "a+") as fp:
                        fp.write(res + "\n")
                print(code(250))
                forward_paths = []
        else:
            res = recognize_cmd()
            command = res[0]
            states = res[1]
            exit_code = res[2]

            if state not in states:
                print(code(503))
                state = 0
            else:
                match command:
                    case "MAIL":
                        state = 1
                    case "RCPT":
                        state = 2
                    case "DATA":
                        state = 3
                print(exit_code)
            path_buffer = ""


def tokenizer_debug(token_name: str):
    global next_char
    if debug:
        print(f"tokenizing <{token_name}> with {next_char=}")


def error(token: str) -> str:
    if debug:
        print(f"error while parsing {token=}")
    return f"ERROR -- {token}"


def code(num: int) -> str:
    match num:
        case 250:
            return "250 OK"
        case 354:
            return "354 Start mail input; end with <CRLF>.<CRLF>"
        case 500:
            return "500 Syntax error: command unrecognized"
        case 501:
            return "501 Syntax error in parameters or arguments"
        case 503:
            return "503 Bad sequence of commands"


def put_next():
    global stream, next_char
    try:
        next_char = next(stream)
    except StopIteration:
        next_char = ""


def consume_str(s: str) -> bool:
    global stream, next_char
    for c in s:
        if next_char != c:
            if debug:
                print(f"searching for '{c}', found '{next_char}'")
            return False
        put_next()
    if debug:
        print(f"found string {s}")
    return True


def recognize_cmd() -> (list, str):  # returns tuple of (command, exit code)
    if next_char == "M":
        return "MAIL", [0], mail_from_cmd()

    if next_char == "R":
        return "RCPT", [1, 2], rcpt_to_cmd()

    if next_char == "D":
        return "DATA", [2], data_cmd()

    return "UNRECOGNIZED", [0, 1, 2], code(500)


def read_data() -> str:
    global next_char, data, data_buffer
    # buffer so we don't attach <CRLF>.<CRLF> to data
    while data_buffer != "\n.\n":
        valid_crlf = next_char == "\n" and (len(data_buffer) in [0, 2])
        valid_period = next_char == "." and len(data_buffer) == 1
        if valid_crlf or valid_period:
            data_buffer += next_char
            put_next()
        elif next_char == "":
            return ""
        else:
            # invalid ending seen, add buffer to data and clear it
            data += data_buffer
            data_buffer = ""
            # after clearing the buffer, insert the next char
            data += next_char
            put_next()
    # buffer was correct ending, so reset buffer and return data
    data_buffer = ""
    out = data
    data = ""  # ensure data line is cleared before next data is read
    return out


def mail_from_cmd():
    # <mail-from-cmd> ::= "MAIL" <whitespace> "FROM:" <nullspace> <reverse-path> <nullspace> <CRLF>
    if not consume_str("MAIL") or whitespace() or not consume_str("FROM:"):
        return code(500)

    if nullspace() or reverse_path() or nullspace() or crlf():
        return code(501)

    return code(250)


def whitespace():
    # <whitespace> ::= <SP> | <SP> <whitespace>
    res = sp()
    if res != "":
        return error("whitespace")

    whitespace()

    return ""


def sp():
    # <SP> ::= the space or tab character
    global stream, next_char
    if next_char in SP:
        put_next()
        return ""
    return error("sp")


def nullspace():
    # <nullspace> ::= <null> | <whitespace>
    whitespace()
    return ""


def null():
    # <null> :== no character
    return ""


def reverse_path():
    # <reverse-path> ::= <path>
    return path()


def path():
    # <path> ::= "<" <mailbox> ">"
    if not consume_str("<"):
        return error("path")

    res = mailbox()
    if res != "":
        return res

    if not consume_str(">"):
        return error("path")

    return ""


def mailbox():
    # <mailbox> ::= <local-part> "@" <domain>
    res = local_part()
    if res != "":
        return res

    if not consume_str("@"):
        return error("mailbox")

    res = domain()
    if res != "":
        return res

    return ""


def local_part():
    # <local-part> ::= <string>
    return string()


def string():
    # <string> ::= <char> | <char> <string>
    res = char()
    if res != "":
        return error("string")

    string()

    return ""


def char():
    # <char> ::= any one of the printable ASCII characters, but not any of <special> or <SP>
    global stream, next_char
    if next_char in SPECIAL or next_char in SP:
        return error("char")
    put_next()
    return ""


def domain():
    # <domain> ::= <element> | <element> "." <domain>
    tokenizer_debug("domain")
    res = element()
    if res != "":
        return res

    if next_char == ".":
        consume_str(".")
        return domain()  # this element is fine, next one also needs to be

    return ""


def element():
    # <element> ::= <letter> | <name>
    tokenizer_debug("element")
    res = letter()
    if res != "":
        return error("element")

    name()

    return ""


def name():
    # <name> ::= <letter> <let-dig-str>
    tokenizer_debug("name")

    res = let_dig_str()
    if res != "":
        return error("name")

    return ""


def letter():
    # <letter> ::= any one of the 52 alphabetic characters A through Z in upper case and a through z in lower case
    global stream, next_char
    if next_char in ALPHA:
        put_next()
        return ""
    return error("letter")


def let_dig_str():
    # <let-dig-str> ::= <let-dig> | <let-dig> <let-dig-str>
    tokenizer_debug("let-dig-str")
    res = let_dig()
    if res != "":
        return error("let-dig-str")

    let_dig_str()

    return ""


def let_dig():
    # <let-dig> ::= <letter> | <digit>
    tokenizer_debug("let-dig")
    res = letter()
    if res != "":
        res = digit()
        if res != "":
            return error("let-dig")
    return ""


def digit():
    # <digit> ::= any one of the ten digits 0 through 9
    global stream, next_char
    if next_char in DIGIT:
        put_next()
        return ""
    return error("digit")


def crlf():
    # <CRLF> ::= the newline character
    global stream, next_char
    if not consume_str("\n"):
        return error("CRLF")
    return ""


def special():
    # <special> ::= "<" | ">" | "(" | ")" | "[" | "]" | "\" | "." | "," | ";" | ":" | "@" | """
    global stream, next_char
    if next_char in SPECIAL:
        put_next()
        return ""
    return error("special")


def rcpt_to_cmd():
    # <rcpt-to-cmd> ::= ["RCPT"] <whitespace> "TO:" <nullspace> <forward-path> <nullspace> <CRLF>
    if not consume_str("RCPT") or whitespace() or not consume_str("TO:"):
        return code(500)

    if nullspace() or forward_path() or nullspace() or crlf():
        return code(501)

    return code(250)


def forward_path():
    # <forward-path> ::= <path>
    return path()


def data_cmd():
    # <data-cmd> ::= "DATA" <nullspace> <CRLF>
    if not consume_str("DATA") or nullspace() or crlf():
        return code(500)

    return code(354)


if __name__ == "__main__":
    main()
