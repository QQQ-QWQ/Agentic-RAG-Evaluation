# Python 程序设计样例资料

## 1. 列表切片

Python 列表切片用于从列表中取出一段连续或按步长间隔的元素。基本语法为：

```python
list[start:stop:step]
```

其中 `start` 表示起始下标，`stop` 表示结束下标但不包含该位置，`step` 表示步长。如果省略 `start`，默认从列表开头开始；如果省略 `stop`，默认取到列表末尾；如果省略 `step`，默认步长为 1。

示例：

```python
nums = [0, 1, 2, 3, 4, 5]
print(nums[1:4])
```

输出结果为：

```text
[1, 2, 3]
```

## 2. for 循环

`for` 循环常用于遍历列表、字符串、字典等可迭代对象。它适合处理“对一组元素逐个执行相同操作”的任务。

示例：

```python
scores = [80, 90, 75]
for score in scores:
    print(score)
```

## 3. 函数

函数用于封装一段可以重复使用的代码。Python 使用 `def` 定义函数。

示例：

```python
def add(a, b):
    return a + b
```

调用 `add(2, 3)` 会返回 `5`。

## 4. 常见错误

`IndexError` 通常表示访问了不存在的下标。例如，列表长度为 3 时，有效下标是 `0`、`1`、`2`，访问 `items[3]` 会导致下标越界错误。

`TypeError` 通常表示操作对象的类型不符合要求。例如，不能直接把字符串和整数相加：

```python
age = 18
print("age=" + age)
```

正确写法可以是：

```python
print("age=" + str(age))
```
