class Example:
    def method(self, x):
        if x > 2 and x < 10:
            return x
        return 0


async def helper(flag):
    if flag:
        return 1
    return 2
