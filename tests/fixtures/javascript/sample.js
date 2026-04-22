export async function fetchThing(x) {
  if (x) return 1;
  return 0;
}

class Demo {
  run() {
    if (true) return 1;
    return 0;
  }
}

const obj = {
  method(y) {
    while (y) {
      return y;
    }
  }
};
