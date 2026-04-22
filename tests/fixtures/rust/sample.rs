pub async fn free_run(x: i32) -> i32 {
    if x > 0 { 1 } else { 0 }
}

impl<T> Service<T> {
    pub async fn run(&self) {
        if true && true {}
    }
}

impl Worker for Service {
    fn work(&self) {
        match 1 { 1 => (), _ => () }
    }
}
