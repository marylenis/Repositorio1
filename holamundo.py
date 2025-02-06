from saludos import saludar

def sumar(num1, num2):
    """
    Esta funcion suma dos numeros
    """
    return num1+num2

def restar(num1,num2):
    """
    Esta funcion resta dos numeros
    """
    return num1-num2

def multiplicar(num1,num2):
    """
    Esta funcion multiplica dos numeros
    """
    return num1*num2



if __name__=='__main__':
    resultado=sumar(2, 4)
    print(resultado)
    print(saludar("Juan"))


