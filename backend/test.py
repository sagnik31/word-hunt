from api import make_guess

res = make_guess("dog")
print(res["rank"], res["similarity"], res["hotness"])
