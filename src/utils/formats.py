__all__ = ("human_join", "plural")


# from rapptz
def human_join(seq, deliminator=", ", final="or"):
    size = len(seq)
    if size == 0:
        return ""

    if size == 1:
        return seq[0]

    if size == 2:
        return f"{seq[0]} {final} {seq[1]}"

    return deliminator.join(seq[:-1]) + f" {final} {seq[-1]}"


# https://github.com/InterStella0/stella_bot/blob/master/utils/useful.py#L199-L205
def plural(text, size):
    logic = size != 1
    target = (("(s)", ("", "s")), ("(is/are)", ("is", "are")))
    for x, y in target:
        text = text.replace(x, y[logic])
    return text
