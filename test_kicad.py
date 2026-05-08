import pcbnew
pgm = getattr(pcbnew, "PgmOrNull", None)
print("pgm:", pgm)
if pgm:
    print("pgm():", pgm())
